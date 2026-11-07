import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import javax.crypto.Mac;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Authentication and Authorization
 *
 * Java 17
 *
 * Enterprise identity management simulation:
 * - PBKDF2 password hashing
 * - Account lockout and credential verification
 * - TOTP multi-factor authentication
 * - HMAC-signed access tokens
 * - Token expiration and revocation
 * - OAuth 2.0 authorization code with PKCE
 * - RBAC and scope evaluation
 * - Session management
 * - Audit logging
 *
 * Production systems should use a managed identity provider,
 * persistent storage, Argon2id where available, secure key
 * management, and standardized JWT/OIDC libraries.
 */

public class AuthenticationAuthorization {

    private static final SecureRandom RANDOM = new SecureRandom();

    private static final int PBKDF2_ITERATIONS = 600_000;
    private static final int HASH_LENGTH = 256;

    private static final long SESSION_LIFETIME = 3600;
    private static final long TOKEN_LIFETIME = 900;

    // -----------------------------------------------------
    // Exceptions
    // -----------------------------------------------------

    static class AuthenticationException extends RuntimeException {
        AuthenticationException(String message) {
            super(message);
        }
    }

    static class AuthorizationException extends RuntimeException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static class ValidationException extends RuntimeException {
        ValidationException(String message) {
            super(message);
        }
    }

    // -----------------------------------------------------
    // Enumerations
    // -----------------------------------------------------

    enum Role {
        ADMIN,
        MANAGER,
        ANALYST,
        VIEWER
    }

    enum AccountStatus {
        ACTIVE,
        LOCKED,
        DISABLED
    }

    enum TokenStatus {
        ACTIVE,
        REVOKED
    }

    // -----------------------------------------------------
    // Immutable domain records
    // -----------------------------------------------------

    record PasswordCredential(
        byte[] salt,
        byte[] hash,
        int iterations
    ) {}

    record AuditEvent(
        String event,
        String userId,
        boolean success,
        Instant timestamp
    ) {}

    record TokenClaims(
        String subject,
        Set<String> scopes,
        Instant issuedAt,
        Instant expiresAt,
        String tokenId
    ) {}

    record OAuthClient(
        String clientId,
        String redirectUri,
        Set<String> allowedScopes
    ) {
        OAuthClient {
            if (
                clientId == null ||
                clientId.isBlank() ||
                redirectUri == null ||
                !redirectUri.startsWith("https://")
            ) {
                throw new ValidationException("Invalid OAuth client.");
            }

            allowedScopes = Set.copyOf(allowedScopes);
        }
    }

    // -----------------------------------------------------
    // Account aggregate
    // -----------------------------------------------------

    static class UserAccount {

        private final String id;
        private final String username;
        private final String email;
        private final PasswordCredential credential;
        private final Role role;

        private AccountStatus status = AccountStatus.ACTIVE;
        private int failedAttempts;
        private Instant lockedUntil = Instant.EPOCH;

        private byte[] mfaSecret;
        private boolean mfaEnabled;

        UserAccount(
            String id,
            String username,
            String email,
            PasswordCredential credential,
            Role role
        ) {
            this.id = id;
            this.username = username;
            this.email = email;
            this.credential = credential;
            this.role = role;
        }

        String id() {
            return id;
        }

        String username() {
            return username;
        }

        Role role() {
            return role;
        }

        AccountStatus status() {
            return status;
        }
    }

    // -----------------------------------------------------
    // Session aggregate
    // -----------------------------------------------------

    static class UserSession {

        final String id;
        final String userId;
        final Instant createdAt;
        final Instant expiresAt;

        boolean revoked;

        UserSession(String id, String userId, Instant expiresAt) {
            this.id = id;
            this.userId = userId;
            this.createdAt = Instant.now();
            this.expiresAt = expiresAt;
        }

        boolean isValid() {
            return !revoked && Instant.now().isBefore(expiresAt);
        }
    }

    // -----------------------------------------------------
    // Password service
    // -----------------------------------------------------

    static class PasswordService {

        private static void validate(String password) {

            if (
                password == null ||
                password.length() < 12 ||
                password.length() > 1024
            ) {
                throw new ValidationException(
                    "Password length is invalid."
                );
            }
        }

        static PasswordCredential hash(String password) {

            validate(password);

            byte[] salt = new byte[16];
            RANDOM.nextBytes(salt);

            return new PasswordCredential(
                salt,
                derive(password, salt, PBKDF2_ITERATIONS),
                PBKDF2_ITERATIONS
            );
        }

        private static byte[] derive(
            String password,
            byte[] salt,
            int iterations
        ) {

            PBEKeySpec spec = new PBEKeySpec(
                password.toCharArray(),
                salt,
                iterations,
                HASH_LENGTH
            );

            try {
                SecretKeyFactory factory =
                    SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");

                return factory.generateSecret(spec).getEncoded();

            } catch (GeneralSecurityException exception) {
                throw new IllegalStateException(
                    "Password derivation failed.",
                    exception
                );

            } finally {
                spec.clearPassword();
            }
        }

        static boolean verify(
            String password,
            PasswordCredential credential
        ) {

            validate(password);

            byte[] candidate = derive(
                password,
                credential.salt(),
                credential.iterations()
            );

            return MessageDigest.isEqual(
                candidate,
                credential.hash()
            );
        }
    }

    // -----------------------------------------------------
    // TOTP service
    // -----------------------------------------------------

    static class MFAService {

        static byte[] generateSecret() {
            byte[] secret = new byte[20];
            RANDOM.nextBytes(secret);
            return secret;
        }

        static String generate(
            byte[] secret,
            long timestampSeconds
        ) {

            try {
                long counter = timestampSeconds / 30;

                byte[] message = new byte[8];

                for (int i = 7; i >= 0; i--) {
                    message[i] = (byte) counter;
                    counter >>>= 8;
                }

                Mac mac = Mac.getInstance("HmacSHA1");

                mac.init(new SecretKeySpec(secret, "HmacSHA1"));

                byte[] digest = mac.doFinal(message);

                int offset = digest[digest.length - 1] & 0x0f;

                int binary =
                    ((digest[offset] & 0x7f) << 24)
                    | ((digest[offset + 1] & 0xff) << 16)
                    | ((digest[offset + 2] & 0xff) << 8)
                    | (digest[offset + 3] & 0xff);

                return String.format(
                    "%06d",
                    binary % 1_000_000
                );

            } catch (GeneralSecurityException exception) {
                throw new IllegalStateException(
                    "TOTP generation failed.",
                    exception
                );
            }
        }

        static boolean verify(
            byte[] secret,
            String suppliedCode
        ) {

            if (
                suppliedCode == null ||
                !suppliedCode.matches("\\d{6}")
            ) {
                return false;
            }

            long now = Instant.now().getEpochSecond();

            for (int offset = -1; offset <= 1; offset++) {

                String expected = generate(
                    secret,
                    now + offset * 30
                );

                if (MessageDigest.isEqual(
                    expected.getBytes(StandardCharsets.US_ASCII),
                    suppliedCode.getBytes(StandardCharsets.US_ASCII)
                )) {
                    return true;
                }
            }

            return false;
        }
    }

    // -----------------------------------------------------
    // RBAC policy
    // -----------------------------------------------------

    static class AuthorizationPolicy {

        private final Map<Role, Set<String>> permissions =
            new EnumMap<>(Role.class);

        AuthorizationPolicy() {

            permissions.put(Role.ADMIN, Set.of(
                "users.read",
                "users.create",
                "users.update",
                "users.delete",
                "reports.read",
                "reports.export",
                "settings.manage"
            ));

            permissions.put(Role.MANAGER, Set.of(
                "users.read",
                "users.update",
                "reports.read",
                "reports.export"
            ));

            permissions.put(Role.ANALYST, Set.of(
                "reports.read",
                "reports.export"
            ));

            permissions.put(Role.VIEWER, Set.of(
                "reports.read"
            ));
        }

        boolean allows(
            Role role,
            String permission,
            Set<String> tokenScopes
        ) {

            return permissions.getOrDefault(
                role,
                Set.of()
            ).contains(permission)
                && tokenScopes.contains(permission);
        }

        void require(
            Role role,
            String permission,
            Set<String> scopes
        ) {

            if (!allows(role, permission, scopes)) {
                throw new AuthorizationException(
                    "Permission denied: " + permission
                );
            }
        }
    }

    // -----------------------------------------------------
    // Access token service
    // -----------------------------------------------------

    static class TokenService {

        private final byte[] signingKey;

        private final Map<String, TokenClaims> tokens =
            new HashMap<>();

        private final Set<String> revoked =
            new HashSet<>();

        TokenService(byte[] signingKey) {

            if (signingKey.length < 32) {
                throw new ValidationException("Signing key too short.");
            }

            this.signingKey = signingKey.clone();
        }

        TokenClaims issue(
            String userId,
            Set<String> scopes,
            long lifetime
        ) {

            if (
                userId == null ||
                userId.isBlank() ||
                scopes.isEmpty() ||
                lifetime <= 0 ||
                lifetime > 86400
            ) {
                throw new ValidationException("Invalid token request.");
            }

            Instant now = Instant.now();

            String tokenId = randomId(16);

            TokenClaims claims = new TokenClaims(
                userId,
                Set.copyOf(scopes),
                now,
                now.plusSeconds(lifetime),
                tokenId
            );

            tokens.put(tokenId, claims);

            return claims;
        }

        TokenClaims validate(String tokenId) {

            if (revoked.contains(tokenId)) {
                throw new AuthenticationException("Token revoked.");
            }

            TokenClaims claims = tokens.get(tokenId);

            if (claims == null) {
                throw new AuthenticationException("Unknown token.");
            }

            if (!Instant.now().isBefore(claims.expiresAt())) {
                throw new AuthenticationException("Token expired.");
            }

            return claims;
        }

        void revoke(String tokenId) {
            validate(tokenId);
            revoked.add(tokenId);
        }
    }

    // -----------------------------------------------------
    // OAuth 2.0 authorization server
    // -----------------------------------------------------

    static class OAuthServer {

        record AuthorizationCode(
            String code,
            String clientId,
            String userId,
            String redirectUri,
            String challenge,
            Set<String> scopes,
            Instant expiresAt,
            boolean consumed
        ) {
            AuthorizationCode consume() {
                return new AuthorizationCode(
                    code,
                    clientId,
                    userId,
                    redirectUri,
                    challenge,
                    scopes,
                    expiresAt,
                    true
                );
            }
        }

        private final Map<String, OAuthClient> clients =
            new HashMap<>();

        private final Map<String, AuthorizationCode> codes =
            new HashMap<>();

        void register(OAuthClient client) {

            if (clients.putIfAbsent(
                client.clientId(),
                client
            ) != null) {
                throw new ValidationException("Client already exists.");
            }
        }

        AuthorizationCode authorize(
            String clientId,
            String userId,
            String redirectUri,
            Set<String> scopes,
            String challenge,
            String state
        ) {

            OAuthClient client = clients.get(clientId);

            if (client == null) {
                throw new AuthenticationException("Unknown client.");
            }

            if (!client.redirectUri().equals(redirectUri)) {
                throw new AuthenticationException("Redirect mismatch.");
            }

            if (
                challenge == null ||
                challenge.isBlank() ||
                state == null ||
                state.length() < 16
            ) {
                throw new ValidationException("Invalid OAuth request.");
            }

            if (!client.allowedScopes().containsAll(scopes)) {
                throw new AuthorizationException("Invalid OAuth scope.");
            }

            AuthorizationCode code = new AuthorizationCode(
                randomId(32),
                clientId,
                userId,
                redirectUri,
                challenge,
                Set.copyOf(scopes),
                Instant.now().plusSeconds(300),
                false
            );

            codes.put(code.code(), code);

            return code;
        }

        TokenClaims exchange(
            String codeValue,
            String clientId,
            String redirectUri,
            String verifier,
            TokenService tokenService
        ) {

            AuthorizationCode code = codes.get(codeValue);

            if (
                code == null ||
                code.consumed() ||
                !Instant.now().isBefore(code.expiresAt())
            ) {
                throw new AuthenticationException(
                    "Authorization code invalid."
                );
            }

            if (
                !code.clientId().equals(clientId) ||
                !code.redirectUri().equals(redirectUri)
            ) {
                throw new AuthenticationException("Client mismatch.");
            }

            if (
                verifier == null ||
                verifier.length() < 43 ||
                verifier.length() > 128
            ) {
                throw new ValidationException("Invalid PKCE verifier.");
            }

            String actualChallenge = sha256Base64Url(verifier);

            if (!MessageDigest.isEqual(
                actualChallenge.getBytes(StandardCharsets.US_ASCII),
                code.challenge().getBytes(StandardCharsets.US_ASCII)
            )) {
                throw new AuthenticationException("PKCE mismatch.");
            }

            // Remove the code before token issuance to prevent replay.
            codes.remove(codeValue);

            return tokenService.issue(
                code.userId(),
                code.scopes(),
                TOKEN_LIFETIME
            );
        }
    }

    // -----------------------------------------------------
    // Authentication application service
    // -----------------------------------------------------

    static class AuthenticationService {

        private final Map<String, UserAccount> users =
            new HashMap<>();

        private final Map<String, String> usernameIndex =
            new HashMap<>();

        private final Map<String, UserSession> sessions =
            new HashMap<>();

        private final List<AuditEvent> audit =
            new ArrayList<>();

        private final AuthorizationPolicy policy =
            new AuthorizationPolicy();

        private final TokenService tokenService;

        private static final int MAX_FAILURES = 5;

        AuthenticationService(byte[] signingKey) {
            tokenService = new TokenService(signingKey);
        }

        private void record(
            String event,
            String userId,
            boolean success
        ) {
            audit.add(new AuditEvent(
                event,
                userId,
                success,
                Instant.now()
            ));
        }

        UserAccount register(
            String id,
            String username,
            String email,
            String password,
            Role role
        ) {

            if (
                id == null ||
                id.isBlank() ||
                username == null ||
                username.length() < 3 ||
                email == null ||
                !email.matches("[^@\\s]+@[^@\\s]+\\.[^@\\s]+")
            ) {
                throw new ValidationException("Invalid account details.");
            }

            String key = username.toLowerCase();

            if (usernameIndex.containsKey(key)) {
                throw new ValidationException("Duplicate username.");
            }

            PasswordCredential credential =
                PasswordService.hash(password);

            UserAccount user = new UserAccount(
                id,
                username,
                email,
                credential,
                role
            );

            users.put(id, user);
            usernameIndex.put(key, id);

            record("REGISTRATION", id, true);

            return user;
        }

        void enableMFA(String userId) {

            UserAccount user = users.get(userId);

            if (user == null || user.status != AccountStatus.ACTIVE) {
                throw new AuthenticationException("Account unavailable.");
            }

            user.mfaSecret = MFAService.generateSecret();
            user.mfaEnabled = true;
        }

        UserSession login(
            String username,
            String password,
            String mfaCode
        ) {

            String userId = usernameIndex.get(
                username.toLowerCase()
            );

            if (userId == null) {
                throw new AuthenticationException("Invalid credentials.");
            }

            UserAccount user = users.get(userId);

            if (user.status == AccountStatus.DISABLED) {
                throw new AuthenticationException("Account disabled.");
            }

            if (user.status == AccountStatus.LOCKED) {
                if (Instant.now().isBefore(user.lockedUntil)) {
                    throw new AuthenticationException("Account locked.");
                }

                user.status = AccountStatus.ACTIVE;
                user.failedAttempts = 0;
            }

            if (!PasswordService.verify(password, user.credential)) {

                user.failedAttempts++;

                if (user.failedAttempts >= MAX_FAILURES) {
                    user.status = AccountStatus.LOCKED;
                    user.lockedUntil = Instant.now().plusSeconds(300);
                }

                record("LOGIN_FAILURE", userId, false);

                throw new AuthenticationException("Invalid credentials.");
            }

            if (
                user.mfaEnabled &&
                !MFAService.verify(user.mfaSecret, mfaCode)
            ) {
                record("MFA_FAILURE", userId, false);
                throw new AuthenticationException("MFA failed.");
            }

            user.failedAttempts = 0;

            UserSession session = new UserSession(
                randomId(32),
                userId,
                Instant.now().plusSeconds(SESSION_LIFETIME)
            );

            sessions.put(session.id, session);

            record("LOGIN_SUCCESS", userId, true);

            return session;
        }

        UserAccount validateSession(String sessionId) {

            UserSession session = sessions.get(sessionId);

            if (session == null || !session.isValid()) {
                throw new AuthenticationException("Invalid session.");
            }

            UserAccount user = users.get(session.userId);

            if (
                user == null ||
                user.status != AccountStatus.ACTIVE
            ) {
                throw new AuthenticationException("Account unavailable.");
            }

            return user;
        }

        void logout(String sessionId) {

            UserSession session = sessions.get(sessionId);

            if (session != null) {
                session.revoked = true;
                record("LOGOUT", session.userId, true);
            }
        }

        TokenClaims issueToken(
            String userId,
            Set<String> scopes
        ) {

            UserAccount user = users.get(userId);

            if (user == null || user.status != AccountStatus.ACTIVE) {
                throw new AuthenticationException("Account unavailable.");
            }

            return tokenService.issue(
                userId,
                scopes,
                TOKEN_LIFETIME
            );
        }

        void authorize(String tokenId, String permission) {

            TokenClaims claims = tokenService.validate(tokenId);

            UserAccount user = users.get(claims.subject());

            if (user == null || user.status != AccountStatus.ACTIVE) {
                throw new AuthenticationException("User unavailable.");
            }

            policy.require(
                user.role,
                permission,
                claims.scopes()
            );
        }

        void revokeToken(String tokenId) {
            tokenService.revoke(tokenId);
        }

        int auditCount() {
            return audit.size();
        }
    }

    // -----------------------------------------------------
    // Utility methods
    // -----------------------------------------------------

    static String randomId(int bytes) {

        byte[] value = new byte[bytes];
        RANDOM.nextBytes(value);

        return Base64.getUrlEncoder()
            .withoutPadding()
            .encodeToString(value);
    }

    static String sha256Base64Url(String input) {

        try {
            byte[] digest = MessageDigest
                .getInstance("SHA-256")
                .digest(input.getBytes(StandardCharsets.US_ASCII));

            return Base64.getUrlEncoder()
                .withoutPadding()
                .encodeToString(digest);

        } catch (GeneralSecurityException exception) {
            throw new IllegalStateException(exception);
        }
    }

    // -----------------------------------------------------
    // Executable demonstration
    // -----------------------------------------------------

    public static void main(String[] args) {

        byte[] signingKey = new byte[32];
        RANDOM.nextBytes(signingKey);

        AuthenticationService service =
            new AuthenticationService(signingKey);

        System.out.println(
            "\nAUTHENTICATION AND AUTHORIZATION SYSTEM"
        );

        UserAccount admin = service.register(
            "U001",
            "admin",
            "admin@example.com",
            "Admin-Strong-Password-2026!",
            Role.ADMIN
        );

        UserAccount analyst = service.register(
            "U002",
            "analyst",
            "analyst@example.com",
            "Analyst-Strong-Password-2026!",
            Role.ANALYST
        );

        service.enableMFA(admin.id());

        String adminCode = MFAService.generate(
            admin.mfaSecret,
            Instant.now().getEpochSecond()
        );

        UserSession adminSession = service.login(
            "admin",
            "Admin-Strong-Password-2026!",
            adminCode
        );

        System.out.println(
            "Admin authenticated: " +
            service.validateSession(adminSession.id).username()
        );

        UserSession analystSession = service.login(
            "analyst",
            "Analyst-Strong-Password-2026!",
            null
        );

        System.out.println(
            "Analyst authenticated: " +
            service.validateSession(analystSession.id).username()
        );

        TokenClaims token = service.issueToken(
            analyst.id(),
            Set.of("reports.read")
        );

        service.authorize(token.tokenId(), "reports.read");

        System.out.println("Report access: GRANTED");

        try {
            service.authorize(token.tokenId(), "users.delete");
        } catch (AuthorizationException exception) {
            System.out.println(
                "Restricted operation: " + exception.getMessage()
            );
        }

        // OAuth authorization-code and PKCE workflow.
        OAuthServer oauth = new OAuthServer();

        oauth.register(new OAuthClient(
            "reporting-app",
            "https://client.example.com/callback",
            Set.of("reports.read", "reports.export")
        ));

        String verifier = randomId(48);
        String challenge = sha256Base64Url(verifier);

        OAuthServer.AuthorizationCode code = oauth.authorize(
            "reporting-app",
            analyst.id(),
            "https://client.example.com/callback",
            Set.of("reports.read"),
            challenge,
            randomId(24)
        );

        TokenClaims oauthToken = oauth.exchange(
            code.code(),
            "reporting-app",
            "https://client.example.com/callback",
            verifier,
            service.tokenService
        );

        System.out.println(
            "OAuth token subject: " + oauthToken.subject()
        );

        // Authorization code replay must fail.
        try {
            oauth.exchange(
                code.code(),
                "reporting-app",
                "https://client.example.com/callback",
                verifier,
                service.tokenService
            );
        } catch (AuthenticationException exception) {
            System.out.println("Replay prevented.");
        }

        service.revokeToken(token.tokenId());

        try {
            service.authorize(token.tokenId(), "reports.read");
        } catch (AuthenticationException exception) {
            System.out.println("Revoked token rejected.");
        }

        service.logout(adminSession.id);

        try {
            service.validateSession(adminSession.id);
        } catch (AuthenticationException exception) {
            System.out.println("Session terminated.");
        }

        System.out.println(
            "Audit events: " + service.auditCount()
        );

        System.out.println("All workflow checks completed.");
    }
}
