#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

/*
 * Authentication and Authorization Engine
 *
 * C++17
 *
 * Demonstrates:
 * - Account registration
 * - Credential verification interface
 * - MFA verification interface
 * - Account lockout
 * - Session creation and expiration
 * - Access token lifecycle
 * - Role-based access control
 * - Scope-based authorization
 * - OAuth authorization-code state management
 * - PKCE verifier/challenge validation
 * - Security audit records
 *
 * The credential and MFA verifiers are deliberately modeled as
 * interfaces. The standard C++ library does not provide secure
 * password hashing, TOTP or cryptographic token signing.
 *
 * Production integrations must supply audited cryptographic
 * implementations, such as Argon2id, HMAC-SHA256 and TOTP.
 */

using namespace std;

using Clock = chrono::system_clock;
using TimePoint = Clock::time_point;

// ---------------------------------------------------------
// Exceptions
// ---------------------------------------------------------

class AuthenticationError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class AuthorizationError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

class ValidationError : public runtime_error {
public:
    using runtime_error::runtime_error;
};

// ---------------------------------------------------------
// Domain types
// ---------------------------------------------------------

enum class Role {
    ADMIN,
    MANAGER,
    ANALYST,
    VIEWER
};

enum class AccountStatus {
    ACTIVE,
    LOCKED,
    DISABLED
};

enum class TokenStatus {
    ACTIVE,
    REVOKED,
    EXPIRED
};

enum class ReviewState {
    NOT_REQUIRED,
    PENDING,
    VERIFIED,
    FAILED
};

string roleName(Role role) {
    switch (role) {
        case Role::ADMIN: return "ADMIN";
        case Role::MANAGER: return "MANAGER";
        case Role::ANALYST: return "ANALYST";
        case Role::VIEWER: return "VIEWER";
    }

    throw ValidationError("Unknown role.");
}

struct User {
    string id;
    string username;
    string credentialVerifier;
    Role role;
    AccountStatus status = AccountStatus::ACTIVE;
    int failedAttempts = 0;
    TimePoint lockedUntil{};
    bool mfaEnabled = false;
};

struct Session {
    string id;
    string userId;
    TimePoint createdAt;
    TimePoint expiresAt;
    bool revoked = false;
};

struct AccessToken {
    string id;
    string userId;
    set<string> scopes;
    TimePoint expiresAt;
    TokenStatus status = TokenStatus::ACTIVE;
};

struct OAuthClient {
    string id;
    string redirectUri;
    set<string> allowedScopes;
};

struct AuthorizationCode {
    string code;
    string clientId;
    string userId;
    string redirectUri;
    string pkceChallenge;
    set<string> scopes;
    TimePoint expiresAt;
    bool consumed = false;
};

struct AuditEvent {
    string event;
    string userId;
    bool success;
    TimePoint timestamp;
};

// ---------------------------------------------------------
// Cryptographic integration interfaces
// ---------------------------------------------------------

class CredentialVerifier {
public:
    virtual ~CredentialVerifier() = default;

    virtual bool verify(
        const string& suppliedCredential,
        const string& storedVerifier
    ) const = 0;
};

class MFAVerifier {
public:
    virtual ~MFAVerifier() = default;

    virtual bool verify(
        const string& userId,
        const string& suppliedCode
    ) const = 0;
};

class PKCEVerifier {
public:
    virtual ~PKCEVerifier() = default;

    virtual bool verify(
        const string& verifier,
        const string& challenge
    ) const = 0;
};

// Demonstration-only verifier. It does not hash passwords.
// Replace it with a secure password-hashing integration.
class DemonstrationCredentialVerifier : public CredentialVerifier {
public:
    bool verify(
        const string& supplied,
        const string& stored
    ) const override {
        if (supplied.size() != stored.size()) {
            return false;
        }

        unsigned char difference = 0;

        for (size_t i = 0; i < supplied.size(); ++i) {
            difference |= static_cast<unsigned char>(
                supplied[i] ^ stored[i]
            );
        }

        return difference == 0;
    }
};

class DemonstrationMFAVerifier : public MFAVerifier {
public:
    bool verify(
        const string&,
        const string& code
    ) const override {
        return code == "654321";
    }
};

// Deterministic PKCE adapter for the executable demonstration.
// It must be replaced with SHA-256 S256 verification.
class DemonstrationPKCEVerifier : public PKCEVerifier {
public:
    bool verify(
        const string& verifier,
        const string& challenge
    ) const override {
        return !verifier.empty() && verifier == challenge;
    }
};

// ---------------------------------------------------------
// Authorization policy
// ---------------------------------------------------------

class AuthorizationPolicy {

private:
    map<Role, set<string>> permissions = {
        {
            Role::ADMIN,
            {
                "users.read",
                "users.create",
                "users.update",
                "users.delete",
                "reports.read",
                "reports.export",
                "settings.manage"
            }
        },
        {
            Role::MANAGER,
            {
                "users.read",
                "users.update",
                "reports.read",
                "reports.export"
            }
        },
        {
            Role::ANALYST,
            {
                "reports.read",
                "reports.export"
            }
        },
        {
            Role::VIEWER,
            {
                "reports.read"
            }
        }
    };

public:
    bool allows(
        Role role,
        const string& permission,
        const set<string>& tokenScopes
    ) const {

        auto iterator = permissions.find(role);

        if (iterator == permissions.end()) {
            return false;
        }

        if (iterator->second.count(permission) == 0) {
            return false;
        }

        return tokenScopes.count(permission) > 0;
    }

    void require(
        Role role,
        const string& permission,
        const set<string>& scopes
    ) const {

        if (!allows(role, permission, scopes)) {
            throw AuthorizationError(
                "Permission denied: " + permission
            );
        }
    }
};

// ---------------------------------------------------------
// Authentication and identity service
// ---------------------------------------------------------

class IdentityService {

private:
    map<string, User> users;
    map<string, string> usernameIndex;
    map<string, Session> sessions;
    map<string, AccessToken> tokens;
    map<string, OAuthClient> clients;
    map<string, AuthorizationCode> authorizationCodes;

    vector<AuditEvent> audit;

    const CredentialVerifier& credentialVerifier;
    const MFAVerifier& mfaVerifier;
    const PKCEVerifier& pkceVerifier;

    AuthorizationPolicy policy;

    static constexpr int MAX_FAILURES = 5;
    static constexpr int LOCKOUT_SECONDS = 300;
    static constexpr int SESSION_SECONDS = 3600;
    static constexpr int TOKEN_SECONDS = 900;

    static TimePoint now() {
        return Clock::now();
    }

    void record(
        const string& event,
        const string& userId,
        bool success
    ) {
        audit.push_back({
            event,
            userId,
            success,
            now()
        });
    }

    static void validatePassword(const string& password) {

        if (password.size() < 12 || password.size() > 1024) {
            throw ValidationError("Invalid password length.");
        }
    }

    const User& findUser(const string& userId) const {

        auto iterator = users.find(userId);

        if (iterator == users.end()) {
            throw AuthenticationError("Unknown user.");
        }

        return iterator->second;
    }

public:
    IdentityService(
        const CredentialVerifier& credential,
        const MFAVerifier& mfa,
        const PKCEVerifier& pkce
    )
        : credentialVerifier(credential),
          mfaVerifier(mfa),
          pkceVerifier(pkce) {}

    void registerUser(
        const string& id,
        const string& username,
        const string& credentialVerifierValue,
        Role role,
        bool mfaEnabled
    ) {

        validatePassword(credentialVerifierValue);

        if (
            id.empty() ||
            username.size() < 3 ||
            usernameIndex.count(username)
        ) {
            throw ValidationError("Invalid or duplicate user.");
        }

        users.emplace(
            id,
            User{
                id,
                username,
                credentialVerifierValue,
                role,
                AccountStatus::ACTIVE,
                0,
                {},
                mfaEnabled
            }
        );

        usernameIndex[username] = id;

        record("REGISTRATION", id, true);
    }

    Session login(
        const string& username,
        const string& password,
        const string& mfaCode = ""
    ) {

        auto index = usernameIndex.find(username);

        if (index == usernameIndex.end()) {
            record("LOGIN_FAILURE", "unknown", false);
            throw AuthenticationError("Invalid credentials.");
        }

        User& user = users.at(index->second);

        if (user.status == AccountStatus::DISABLED) {
            throw AuthenticationError("Account disabled.");
        }

        if (user.status == AccountStatus::LOCKED) {

            if (now() < user.lockedUntil) {
                throw AuthenticationError("Account locked.");
            }

            user.status = AccountStatus::ACTIVE;
            user.failedAttempts = 0;
        }

        if (!credentialVerifier.verify(
            password,
            user.credentialVerifier
        )) {

            ++user.failedAttempts;

            if (user.failedAttempts >= MAX_FAILURES) {
                user.status = AccountStatus::LOCKED;
                user.lockedUntil =
                    now() + chrono::seconds(LOCKOUT_SECONDS);
            }

            record("LOGIN_FAILURE", user.id, false);

            throw AuthenticationError("Invalid credentials.");
        }

        if (
            user.mfaEnabled &&
            !mfaVerifier.verify(user.id, mfaCode)
        ) {
            record("MFA_FAILURE", user.id, false);
            throw AuthenticationError("MFA verification failed.");
        }

        user.failedAttempts = 0;

        Session session{
            "session-" + to_string(sessions.size() + 1),
            user.id,
            now(),
            now() + chrono::seconds(SESSION_SECONDS),
            false
        };

        sessions.emplace(session.id, session);

        record("LOGIN_SUCCESS", user.id, true);

        return session;
    }

    const User& validateSession(const string& sessionId) const {

        auto iterator = sessions.find(sessionId);

        if (iterator == sessions.end()) {
            throw AuthenticationError("Session not found.");
        }

        const Session& session = iterator->second;

        if (
            session.revoked ||
            session.expiresAt <= now()
        ) {
            throw AuthenticationError("Session invalid.");
        }

        const User& user = findUser(session.userId);

        if (user.status != AccountStatus::ACTIVE) {
            throw AuthenticationError("Account unavailable.");
        }

        return user;
    }

    void logout(const string& sessionId) {

        auto iterator = sessions.find(sessionId);

        if (iterator != sessions.end()) {
            iterator->second.revoked = true;

            record(
                "LOGOUT",
                iterator->second.userId,
                true
            );
        }
    }

    AccessToken issueToken(
        const string& userId,
        set<string> scopes
    ) {

        const User& user = findUser(userId);

        if (user.status != AccountStatus::ACTIVE || scopes.empty()) {
            throw AuthenticationError("Token issuance denied.");
        }

        for (const auto& scope : scopes) {
            if (scope.empty()) {
                throw ValidationError("Invalid token scope.");
            }
        }

        AccessToken token{
            "token-" + to_string(tokens.size() + 1),
            userId,
            move(scopes),
            now() + chrono::seconds(TOKEN_SECONDS),
            TokenStatus::ACTIVE
        };

        tokens.emplace(token.id, token);

        record("TOKEN_ISSUED", userId, true);

        return token;
    }

    const AccessToken& validateToken(const string& tokenId) const {

        auto iterator = tokens.find(tokenId);

        if (iterator == tokens.end()) {
            throw AuthenticationError("Unknown token.");
        }

        const AccessToken& token = iterator->second;

        if (token.status != TokenStatus::ACTIVE) {
            throw AuthenticationError("Token inactive.");
        }

        if (token.expiresAt <= now()) {
            throw AuthenticationError("Token expired.");
        }

        const User& user = findUser(token.userId);

        if (user.status != AccountStatus::ACTIVE) {
            throw AuthenticationError("Account unavailable.");
        }

        return token;
    }

    void revokeToken(const string& tokenId) {

        auto iterator = tokens.find(tokenId);

        if (iterator == tokens.end()) {
            throw AuthenticationError("Unknown token.");
        }

        iterator->second.status = TokenStatus::REVOKED;

        record(
            "TOKEN_REVOKED",
            iterator->second.userId,
            true
        );
    }

    void authorize(
        const string& tokenId,
        const string& permission
    ) const {

        const AccessToken& token = validateToken(tokenId);
        const User& user = findUser(token.userId);

        policy.require(
            user.role,
            permission,
            token.scopes
        );
    }

    // OAuth client registration.
    void registerClient(OAuthClient client) {

        if (
            client.id.empty() ||
            client.redirectUri.rfind("https://", 0) != 0 ||
            clients.count(client.id)
        ) {
            throw ValidationError("Invalid OAuth client.");
        }

        clients.emplace(client.id, move(client));
    }

    // Issue a short-lived authorization code.
    AuthorizationCode authorizeClient(
        const string& clientId,
        const string& userId,
        const string& redirectUri,
        set<string> scopes,
        const string& challenge,
        const string& state
    ) {

        auto clientIterator = clients.find(clientId);

        if (clientIterator == clients.end()) {
            throw AuthenticationError("Unknown OAuth client.");
        }

        const OAuthClient& client = clientIterator->second;

        if (
            redirectUri != client.redirectUri ||
            challenge.empty() ||
            state.size() < 16
        ) {
            throw AuthenticationError("Invalid OAuth request.");
        }

        for (const auto& scope : scopes) {
            if (client.allowedScopes.count(scope) == 0) {
                throw AuthorizationError("Unauthorized OAuth scope.");
            }
        }

        const User& user = findUser(userId);

        if (user.status != AccountStatus::ACTIVE) {
            throw AuthenticationError("User unavailable.");
        }

        AuthorizationCode code{
            "code-" + to_string(authorizationCodes.size() + 1),
            clientId,
            userId,
            redirectUri,
            challenge,
            move(scopes),
            now() + chrono::minutes(5),
            false
        };

        authorizationCodes.emplace(code.code, code);

        return code;
    }

    AccessToken exchangeCode(
        const string& codeValue,
        const string& clientId,
        const string& redirectUri,
        const string& verifier
    ) {

        auto iterator = authorizationCodes.find(codeValue);

        if (iterator == authorizationCodes.end()) {
            throw AuthenticationError("Invalid authorization code.");
        }

        AuthorizationCode& code = iterator->second;

        if (
            code.consumed ||
            code.expiresAt <= now() ||
            code.clientId != clientId ||
            code.redirectUri != redirectUri
        ) {
            throw AuthenticationError("Authorization code rejected.");
        }

        if (
            verifier.size() < 43 ||
            verifier.size() > 128 ||
            !pkceVerifier.verify(verifier, code.pkceChallenge)
        ) {
            throw AuthenticationError("PKCE verification failed.");
        }

        // Consume the code before issuing an access token.
        code.consumed = true;

        return issueToken(code.userId, code.scopes);
    }

    size_t auditCount() const {
        return audit.size();
    }
};

// ---------------------------------------------------------
// Main demonstration
// ---------------------------------------------------------

int main() {

    try {

        DemonstrationCredentialVerifier credentialVerifier;
        DemonstrationMFAVerifier mfaVerifier;
        DemonstrationPKCEVerifier pkceVerifier;

        IdentityService identity(
            credentialVerifier,
            mfaVerifier,
            pkceVerifier
        );

        cout << "\nAUTHENTICATION AND AUTHORIZATION ENGINE\n";

        identity.registerUser(
            "U001",
            "admin",
            "Admin-Strong-Password-2026!",
            Role::ADMIN,
            true
        );

        identity.registerUser(
            "U002",
            "analyst",
            "Analyst-Strong-Password-2026!",
            Role::ANALYST,
            false
        );

        Session adminSession = identity.login(
            "admin",
            "Admin-Strong-Password-2026!",
            "654321"
        );

        cout << "Admin authenticated: "
             << identity.validateSession(adminSession.id).username
             << '\n';

        Session analystSession = identity.login(
            "analyst",
            "Analyst-Strong-Password-2026!"
        );

        const User& analyst = identity.validateSession(
            analystSession.id
        );

        cout << "Analyst authenticated: "
             << analyst.username << '\n';

        AccessToken token = identity.issueToken(
            analyst.id,
            {"reports.read"}
        );

        identity.authorize(token.id, "reports.read");

        cout << "Report authorization: GRANTED\n";

        try {
            identity.authorize(token.id, "users.delete");
        }
        catch (const AuthorizationError& error) {
            cout << "Restricted operation: "
                 << error.what() << '\n';
        }

        // OAuth and PKCE demonstration.
        identity.registerClient({
            "reporting-app",
            "https://client.example.com/callback",
            {"reports.read", "reports.export"}
        });

        const string verifier =
            "0123456789012345678901234567890123456789012";

        const string challenge = verifier;

        AuthorizationCode code = identity.authorizeClient(
            "reporting-app",
            analyst.id,
            "https://client.example.com/callback",
            {"reports.read"},
            challenge,
            "state-value-123456789"
        );

        AccessToken oauthToken = identity.exchangeCode(
            code.code,
            "reporting-app",
            "https://client.example.com/callback",
            verifier
        );

        cout << "OAuth token issued: "
             << oauthToken.id << '\n';

        // Authorization-code replay protection.
        try {
            identity.exchangeCode(
                code.code,
                "reporting-app",
                "https://client.example.com/callback",
                verifier
            );
        }
        catch (const AuthenticationError& error) {
            cout << "Code replay prevented: "
                 << error.what() << '\n';
        }

        // Token revocation.
        identity.revokeToken(token.id);

        try {
            identity.validateToken(token.id);
        }
        catch (const AuthenticationError& error) {
            cout << "Revoked token rejected: "
                 << error.what() << '\n';
        }

        // Session revocation.
        identity.logout(adminSession.id);

        try {
            identity.validateSession(adminSession.id);
        }
        catch (const AuthenticationError& error) {
            cout << "Session terminated: "
                 << error.what() << '\n';
        }

        cout << "Audit records: "
             << identity.auditCount() << '\n';

        cout << "Workflow completed successfully.\n";
    }
    catch (const exception& error) {
        cerr << "Application failure: "
             << error.what() << '\n';

        return 1;
    }

    return 0;
}
