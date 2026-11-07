'use strict';

/**
 * Authentication and Authorization
 *
 * Node.js 20+
 *
 * Features:
 * - Password hashing with scrypt
 * - Timing-safe password verification
 * - Asynchronous authentication
 * - TOTP-based MFA
 * - HMAC-signed access tokens
 * - Token revocation and expiration
 * - OAuth 2.0 authorization code with PKCE
 * - RBAC and scope-based access control
 * - Session lifecycle
 * - Event-driven security auditing
 *
 * Production systems should use a dedicated identity provider,
 * durable storage, secure cookie settings and managed signing keys.
 */

const crypto = require('node:crypto');
const { EventEmitter } = require('node:events');

const CONFIG = Object.freeze({
    passwordLength: 12,
    scryptCost: 16384,
    scryptBlockSize: 8,
    scryptParallelization: 1,
    keyLength: 64,
    tokenLifetime: 900,
    sessionLifetime: 3600,
    lockoutThreshold: 5,
    lockoutDuration: 300000
});

class AuthenticationError extends Error {}
class AuthorizationError extends Error {}
class ValidationError extends Error {}

const Roles = Object.freeze({
    ADMIN: 'admin',
    MANAGER: 'manager',
    ANALYST: 'analyst',
    VIEWER: 'viewer'
});

const Permissions = Object.freeze({
    admin: new Set([
        'users.read',
        'users.create',
        'users.update',
        'users.delete',
        'reports.read',
        'reports.export',
        'settings.manage'
    ]),

    manager: new Set([
        'users.read',
        'users.update',
        'reports.read',
        'reports.export'
    ]),

    analyst: new Set([
        'reports.read',
        'reports.export'
    ]),

    viewer: new Set([
        'reports.read'
    ])
});

function randomId(bytes = 32) {
    return crypto.randomBytes(bytes).toString('base64url');
}

function timingSafeEqualString(first, second) {
    const a = Buffer.from(first);
    const b = Buffer.from(second);

    return a.length === b.length &&
        crypto.timingSafeEqual(a, b);
}

// ---------------------------------------------------------
// Password manager
// ---------------------------------------------------------

class PasswordManager {

    static validate(password) {

        if (typeof password !== 'string') {
            throw new ValidationError('Password must be a string.');
        }

        if (
            password.length < CONFIG.passwordLength ||
            Buffer.byteLength(password, 'utf8') > 1024
        ) {
            throw new ValidationError('Password length is invalid.');
        }
    }

    static async hash(password) {

        this.validate(password);

        const salt = crypto.randomBytes(16);

        const derivedKey = await new Promise((resolve, reject) => {

            crypto.scrypt(
                password,
                salt,
                CONFIG.keyLength,
                {
                    N: CONFIG.scryptCost,
                    r: CONFIG.scryptBlockSize,
                    p: CONFIG.scryptParallelization,
                    maxmem: 64 * 1024 * 1024
                },
                (error, key) => {
                    if (error) reject(error);
                    else resolve(key);
                }
            );
        });

        return {
            salt: salt.toString('base64'),
            hash: derivedKey.toString('base64'),
            algorithm: 'scrypt'
        };
    }

    static async verify(password, stored) {

        const candidate = await this.hashWithSalt(
            password,
            Buffer.from(stored.salt, 'base64')
        );

        return timingSafeEqualString(
            candidate.toString('base64'),
            stored.hash
        );
    }

    static async hashWithSalt(password, salt) {

        return new Promise((resolve, reject) => {

            crypto.scrypt(
                password,
                salt,
                CONFIG.keyLength,
                {
                    N: CONFIG.scryptCost,
                    r: CONFIG.scryptBlockSize,
                    p: CONFIG.scryptParallelization,
                    maxmem: 64 * 1024 * 1024
                },
                (error, key) => {
                    if (error) reject(error);
                    else resolve(key);
                }
            );
        });
    }
}

// ---------------------------------------------------------
// TOTP MFA
// ---------------------------------------------------------

class MFAService {

    static createSecret() {
        return crypto.randomBytes(20);
    }

    static generate(secret, timestamp = Date.now()) {

        const counter = BigInt(
            Math.floor(timestamp / 1000 / 30)
        );

        const message = Buffer.alloc(8);
        message.writeBigUInt64BE(counter);

        const digest = crypto
            .createHmac('sha1', secret)
            .update(message)
            .digest();

        const offset = digest[digest.length - 1] & 0x0f;

        const binary = digest.readUInt32BE(offset) & 0x7fffffff;

        return String(binary % 1000000).padStart(6, '0');
    }

    static verify(secret, suppliedCode, timestamp = Date.now()) {

        if (!/^\d{6}$/.test(suppliedCode)) {
            return false;
        }

        for (let offset = -1; offset <= 1; offset++) {

            const expected = this.generate(
                secret,
                timestamp + offset * 30000
            );

            if (timingSafeEqualString(expected, suppliedCode)) {
                return true;
            }
        }

        return false;
    }
}

// ---------------------------------------------------------
// Token service
// ---------------------------------------------------------

class TokenService {

    constructor(secret = crypto.randomBytes(32)) {

        if (secret.length < 32) {
            throw new ValidationError('Signing key is too short.');
        }

        this.secret = secret;
        this.revoked = new Set();
    }

    issue(userId, scopes, lifetime = CONFIG.tokenLifetime) {

        if (
            typeof userId !== 'string' ||
            !userId ||
            !Array.isArray(scopes) ||
            lifetime <= 0 ||
            lifetime > 86400
        ) {
            throw new ValidationError('Invalid token parameters.');
        }

        const now = Math.floor(Date.now() / 1000);

        const header = {
            alg: 'HS256',
            typ: 'JWT'
        };

        const payload = {
            sub: userId,
            scope: [...new Set(scopes)].sort(),
            iat: now,
            exp: now + lifetime,
            jti: randomId(16)
        };

        const encode = value =>
            Buffer.from(JSON.stringify(value)).toString('base64url');

        const unsigned = `${encode(header)}.${encode(payload)}`;

        const signature = crypto
            .createHmac('sha256', this.secret)
            .update(unsigned)
            .digest('base64url');

        return `${unsigned}.${signature}`;
    }

    verify(token) {

        if (typeof token !== 'string' || this.revoked.has(token)) {
            throw new AuthenticationError('Token unavailable.');
        }

        const parts = token.split('.');

        if (parts.length !== 3) {
            throw new AuthenticationError('Malformed token.');
        }

        let header;
        let payload;

        try {
            header = JSON.parse(
                Buffer.from(parts[0], 'base64url').toString()
            );

            payload = JSON.parse(
                Buffer.from(parts[1], 'base64url').toString()
            );
        } catch {
            throw new AuthenticationError('Invalid token encoding.');
        }

        if (
            header.alg !== 'HS256' ||
            header.typ !== 'JWT'
        ) {
            throw new AuthenticationError('Unsupported token algorithm.');
        }

        const unsigned = `${parts[0]}.${parts[1]}`;

        const expected = crypto
            .createHmac('sha256', this.secret)
            .update(unsigned)
            .digest('base64url');

        if (!timingSafeEqualString(expected, parts[2])) {
            throw new AuthenticationError('Invalid signature.');
        }

        const now = Math.floor(Date.now() / 1000);

        if (
            typeof payload.sub !== 'string' ||
            !Array.isArray(payload.scope) ||
            typeof payload.exp !== 'number' ||
            typeof payload.iat !== 'number' ||
            typeof payload.jti !== 'string' ||
            payload.exp <= now ||
            payload.iat > now + 30 ||
            !payload.scope.every(s => typeof s === 'string')
        ) {
            throw new AuthenticationError('Invalid token claims.');
        }

        return Object.freeze(payload);
    }

    revoke(token) {
        this.verify(token);
        this.revoked.add(token);
    }
}

// ---------------------------------------------------------
// RBAC and policy evaluation
// ---------------------------------------------------------

class AuthorizationService {

    static evaluate(user, permission, tokenScopes = null) {

        if (!user || !Object.hasOwn(Permissions, user.role)) {
            return false;
        }

        const allowed = Permissions[user.role].has(permission);

        if (!allowed) return false;

        if (tokenScopes !== null) {
            return tokenScopes.has(permission);
        }

        return true;
    }

    static require(user, permission, scopes = null) {

        if (!this.evaluate(user, permission, scopes)) {
            throw new AuthorizationError(
                `Permission denied: ${permission}`
            );
        }
    }
}

// ---------------------------------------------------------
// OAuth authorization server simulation
// ---------------------------------------------------------

class OAuthServer {

    constructor() {
        this.clients = new Map();
        this.codes = new Map();
    }

    registerClient(client) {

        const redirect = new URL(client.redirectUri);

        if (
            redirect.protocol !== 'https:' ||
            this.clients.has(client.clientId)
        ) {
            throw new ValidationError('Invalid OAuth client.');
        }

        this.clients.set(client.clientId, {
            ...client,
            allowedScopes: new Set(client.allowedScopes)
        });
    }

    authorize({
        clientId,
        userId,
        redirectUri,
        scopes,
        challenge,
        state
    }) {

        const client = this.clients.get(clientId);

        if (!client) {
            throw new AuthenticationError('Unknown client.');
        }

        if (redirectUri !== client.redirectUri) {
            throw new AuthenticationError('Redirect URI mismatch.');
        }

        if (!state || state.length < 16 || !challenge) {
            throw new ValidationError('State and PKCE are required.');
        }

        if (!scopes.every(scope => client.allowedScopes.has(scope))) {
            throw new AuthorizationError('Invalid OAuth scope.');
        }

        const code = randomId(32);

        this.codes.set(code, {
            clientId,
            userId,
            redirectUri,
            challenge,
            scopes: new Set(scopes),
            expiresAt: Date.now() + 300000,
            consumed: false
        });

        return { code, state };
    }

    exchange({
        code,
        clientId,
        redirectUri,
        verifier
    }) {

        const record = this.codes.get(code);

        if (
            !record ||
            record.consumed ||
            record.expiresAt <= Date.now()
        ) {
            throw new AuthenticationError('Invalid authorization code.');
        }

        if (
            record.clientId !== clientId ||
            record.redirectUri !== redirectUri
        ) {
            throw new AuthenticationError('OAuth client mismatch.');
        }

        if (typeof verifier !== 'string' ||
            verifier.length < 43 ||
            verifier.length > 128
        ) {
            throw new ValidationError('Invalid PKCE verifier.');
        }

        const challenge = crypto
            .createHash('sha256')
            .update(verifier)
            .digest('base64url');

        if (!timingSafeEqualString(challenge, record.challenge)) {
            throw new AuthenticationError('PKCE verification failed.');
        }

        record.consumed = true;

        return {
            userId: record.userId,
            scopes: new Set(record.scopes)
        };
    }
}

// ---------------------------------------------------------
// Authentication service
// ---------------------------------------------------------

class AuthenticationService extends EventEmitter {

    constructor() {
        super();

        this.users = new Map();
        this.sessions = new Map();
        this.tokens = new TokenService();
    }

    async register(username, email, password, role) {

        if (
            typeof username !== 'string' ||
            username.length < 3 ||
            !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ||
            !Object.hasOwn(Permissions, role)
        ) {
            throw new ValidationError('Invalid registration data.');
        }

        const key = username.toLowerCase();

        if ([...this.users.values()].some(
            user => user.username.toLowerCase() === key
        )) {
            throw new ValidationError('Username already exists.');
        }

        const passwordRecord = await PasswordManager.hash(password);

        const user = {
            id: randomId(16),
            username,
            email,
            role,
            passwordRecord,
            status: 'active',
            failedAttempts: 0,
            lockedUntil: 0,
            mfaSecret: null,
            mfaEnabled: false
        };

        this.users.set(user.id, user);

        this.emit('security-event', {
            type: 'USER_REGISTERED',
            userId: user.id,
            timestamp: Date.now()
        });

        return user;
    }

    enableMFA(userId) {

        const user = this.users.get(userId);

        if (!user || user.status !== 'active') {
            throw new AuthenticationError('Account unavailable.');
        }

        user.mfaSecret = MFAService.createSecret();
        user.mfaEnabled = true;

        return user.mfaSecret.toString('base64');
    }

    async login(username, password, mfaCode = null) {

        const user = [...this.users.values()].find(
            entry => entry.username.toLowerCase() ===
                String(username).toLowerCase()
        );

        if (!user) {
            throw new AuthenticationError('Invalid credentials.');
        }

        if (user.status === 'disabled') {
            throw new AuthenticationError('Account disabled.');
        }

        if (user.lockedUntil > Date.now()) {
            throw new AuthenticationError('Account locked.');
        }

        const validPassword = await PasswordManager.verify(
            password,
            user.passwordRecord
        );

        if (!validPassword) {

            user.failedAttempts++;

            if (user.failedAttempts >= CONFIG.lockoutThreshold) {
                user.lockedUntil = Date.now() + CONFIG.lockoutDuration;
            }

            this.emit('security-event', {
                type: 'LOGIN_FAILURE',
                userId: user.id,
                timestamp: Date.now()
            });

            throw new AuthenticationError('Invalid credentials.');
        }

        if (user.mfaEnabled &&
            !MFAService.verify(user.mfaSecret, mfaCode || '')) {

            throw new AuthenticationError('MFA verification failed.');
        }

        user.failedAttempts = 0;

        const session = {
            id: randomId(32),
            userId: user.id,
            createdAt: Date.now(),
            expiresAt: Date.now() + CONFIG.sessionLifetime * 1000,
            revoked: false
        };

        this.sessions.set(session.id, session);

        this.emit('security-event', {
            type: 'LOGIN_SUCCESS',
            userId: user.id,
            timestamp: Date.now()
        });

        return session;
    }

    validateSession(sessionId) {

        const session = this.sessions.get(sessionId);

        if (
            !session ||
            session.revoked ||
            session.expiresAt <= Date.now()
        ) {
            throw new AuthenticationError('Invalid session.');
        }

        const user = this.users.get(session.userId);

        if (!user || user.status !== 'active') {
            throw new AuthenticationError('Account unavailable.');
        }

        return user;
    }

    logout(sessionId) {

        const session = this.sessions.get(sessionId);

        if (session) {
            session.revoked = true;

            this.emit('security-event', {
                type: 'LOGOUT',
                userId: session.userId,
                timestamp: Date.now()
            });
        }
    }
}

// ---------------------------------------------------------
// Executable demonstration
// ---------------------------------------------------------

async function main() {

    const auth = new AuthenticationService();

    auth.on('security-event', event => {
        console.log(
            'AUDIT:',
            event.type,
            event.userId
        );
    });

    const admin = await auth.register(
        'admin',
        'admin@example.com',
        'Admin-Strong-Password-2026!',
        Roles.ADMIN
    );

    const analyst = await auth.register(
        'analyst',
        'analyst@example.com',
        'Analyst-Strong-Password-2026!',
        Roles.ANALYST
    );

    auth.enableMFA(admin.id);

    const adminCode = MFAService.generate(admin.mfaSecret);

    const adminSession = await auth.login(
        'admin',
        'Admin-Strong-Password-2026!',
        adminCode
    );

    console.log(
        'Admin authenticated:',
        auth.validateSession(adminSession.id).username
    );

    const analystSession = await auth.login(
        'analyst',
        'Analyst-Strong-Password-2026!'
    );

    const authenticatedAnalyst = auth.validateSession(
        analystSession.id
    );

    console.log(
        'Analyst report access:',
        AuthorizationService.evaluate(
            authenticatedAnalyst,
            'reports.read'
        )
    );

    console.log(
        'Analyst user deletion:',
        AuthorizationService.evaluate(
            authenticatedAnalyst,
            'users.delete'
        )
    );

    const token = auth.tokens.issue(
        analyst.id,
        ['reports.read']
    );

    const claims = auth.tokens.verify(token);

    AuthorizationService.require(
        authenticatedAnalyst,
        'reports.read',
        new Set(claims.scope)
    );

    console.log('Access token accepted.');

    // OAuth 2.0 authorization code and PKCE.
    const oauth = new OAuthServer();

    oauth.registerClient({
        clientId: 'reporting-app',
        redirectUri: 'https://client.example.com/callback',
        allowedScopes: ['reports.read', 'reports.export']
    });

    const verifier = randomId(48);

    const challenge = crypto
        .createHash('sha256')
        .update(verifier)
        .digest('base64url');

    const authorization = oauth.authorize({
        clientId: 'reporting-app',
        userId: analyst.id,
        redirectUri: 'https://client.example.com/callback',
        scopes: ['reports.read'],
        challenge,
        state: randomId(24)
    });

    const oauthResult = oauth.exchange({
        code: authorization.code,
        clientId: 'reporting-app',
        redirectUri: 'https://client.example.com/callback',
        verifier
    });

    console.log('OAuth subject:', oauthResult.userId);
    console.log('OAuth scopes:', [...oauthResult.scopes]);

    // Replay attempt.
    try {
        oauth.exchange({
            code: authorization.code,
            clientId: 'reporting-app',
            redirectUri: 'https://client.example.com/callback',
            verifier
        });
    } catch (error) {
        console.log('Replay rejected:', error.message);
    }

    // Revocation.
    auth.tokens.revoke(token);

    try {
        auth.tokens.verify(token);
    } catch (error) {
        console.log('Revocation verified:', error.message);
    }

    auth.logout(adminSession.id);

    try {
        auth.validateSession(adminSession.id);
    } catch (error) {
        console.log('Session terminated:', error.message);
    }

    console.log('Authentication workflow completed.');
}

main().catch(error => {
    console.error('Application error:', error.message);
    process.exitCode = 1;
});
