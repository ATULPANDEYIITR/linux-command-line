'use strict';

/*
 * Users, Groups, Permissions, Authentication, and Privilege Management
 * =====================================================================
 *
 * This JavaScript file complements the Linux-oriented Python study program.
 *
 * It uses:
 *   1. A portable in-memory Unix-like permission model.
 *   2. Node.js APIs for observing the current process.
 *   3. Safe read-only filesystem inspection.
 *   4. Permission evaluation and testing.
 *   5. A small role/privilege model to connect operating-system concepts
 *      with application authorization.
 *
 * No user, group, password, ownership, or permission-changing operation
 * is performed automatically.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

function section(title) {
    console.log('\n' + '='.repeat(78));
    console.log(title);
    console.log('='.repeat(78));
}

function subsection(title) {
    console.log(`\n--- ${title} ---`);
}

function yesNo(value) {
    return value ? 'yes' : 'no';
}

// ---------------------------------------------------------------------------
// 1. Process identity
// ---------------------------------------------------------------------------

function demonstrateProcessIdentity() {
    section('1. Node.js process identity');

    console.log(`Platform: ${process.platform}`);
    console.log(`Architecture: ${process.arch}`);
    console.log(`Node.js version: ${process.version}`);
    console.log(`Process UID: ${typeof process.getuid === 'function' ? process.getuid() : 'not exposed'}`);
    console.log(`Effective UID: ${typeof process.geteuid === 'function' ? process.geteuid() : 'not exposed'}`);
    console.log(`Process GID: ${typeof process.getgid === 'function' ? process.getgid() : 'not exposed'}`);
    console.log(`Effective GID: ${typeof process.getegid === 'function' ? process.getegid() : 'not exposed'}`);

    if (typeof process.getgroups === 'function') {
        console.log(`Supplementary groups: ${process.getgroups().join(', ')}`);
    } else {
        console.log('Supplementary group API is not exposed on this platform.');
    }
}

// ---------------------------------------------------------------------------
// 2. Portable permission model
// ---------------------------------------------------------------------------

const PERMISSIONS = Object.freeze({
    READ: 4,
    WRITE: 2,
    EXECUTE: 1
});

class Identity {
    constructor(uid, primaryGid, supplementaryGids = []) {
        this.uid = uid;
        this.primaryGid = primaryGid;
        this.supplementaryGids = new Set(supplementaryGids);
    }

    hasGroup(gid) {
        return gid === this.primaryGid || this.supplementaryGids.has(gid);
    }
}

class PermissionObject {
    constructor(ownerUid, groupGid, mode) {
        this.ownerUid = ownerUid;
        this.groupGid = groupGid;
        this.mode = mode;
    }
}

function selectPermissionClass(identity, object) {
    // Unix-style owner/group/other evaluation selects one applicable class.
    if (identity.uid === object.ownerUid) {
        return 'owner';
    }

    if (identity.hasGroup(object.groupGid)) {
        return 'group';
    }

    return 'other';
}

function classShift(permissionClass) {
    return {
        owner: 6,
        group: 3,
        other: 0
    }[permissionClass];
}

function canAccess(identity, object, requestedPermission) {
    const value = PERMISSIONS[requestedPermission];

    if (!value) {
        throw new Error('Permission must be READ, WRITE, or EXECUTE.');
    }

    const selectedClass = selectPermissionClass(identity, object);
    const shift = classShift(selectedClass);

    return Boolean(((object.mode >> shift) & value) !== 0);
}

function modeToSymbolic(mode, directory = false) {
    const prefix = directory ? 'd' : '-';

    function triplet(shift) {
        const read = (mode >> shift) & 4;
        const write = (mode >> shift) & 2;
        const execute = (mode >> shift) & 1;

        return [
            read ? 'r' : '-',
            write ? 'w' : '-',
            execute ? 'x' : '-'
        ].join('');
    }

    return `${prefix}${triplet(6)}${triplet(3)}${triplet(0)}`;
}

function demonstratePermissionModel() {
    section('2. Unix-like permission evaluation');

    const owner = new Identity(1000, 100);
    const groupMember = new Identity(1001, 100);
    const supplementaryGroupMember = new Identity(1002, 200, [100]);
    const outsider = new Identity(1003, 300);

    const object = new PermissionObject(1000, 100, 0o640);

    console.log(`Object mode: ${object.mode.toString(8)}`);
    console.log(`Symbolic mode: ${modeToSymbolic(object.mode)}`);

    const identities = [
        ['owner', owner],
        ['group member', groupMember],
        ['supplementary group member', supplementaryGroupMember],
        ['outsider', outsider]
    ];

    for (const [name, identity] of identities) {
        console.log(`\n${name}`);
        console.log(`  selected class: ${selectPermissionClass(identity, object)}`);

        for (const permission of ['READ', 'WRITE', 'EXECUTE']) {
            console.log(
                `  ${permission.toLowerCase()}: ${yesNo(
                    canAccess(identity, object, permission)
                )}`
            );
        }
    }
}

// ---------------------------------------------------------------------------
// 3. chmod and umask calculations
// ---------------------------------------------------------------------------

function calculateCreationMode(requestedMode, umask) {
    // The standard conceptual model masks requested permission bits.
    return requestedMode & (~umask);
}

function demonstrateModesAndUmask() {
    section('3. chmod notation and umask');

    const examples = [0o600, 0o640, 0o644, 0o700, 0o750, 0o755, 0o777];

    for (const mode of examples) {
        console.log(
            `${mode.toString(8).padStart(3, '0')} -> ${modeToSymbolic(mode)}`
        );
    }

    subsection('Creation with umask');

    for (const umask of [0o022, 0o027, 0o077]) {
        const fileMode = calculateCreationMode(0o666, umask);
        const directoryMode = calculateCreationMode(0o777, umask);

        console.log(
            `umask ${umask.toString(8).padStart(3, '0')} -> ` +
            `file ${fileMode.toString(8)}, directory ${directoryMode.toString(8)}`
        );
    }
}

// ---------------------------------------------------------------------------
// 4. Real filesystem inspection
// ---------------------------------------------------------------------------

function inspectFilesystemObject(targetPath) {
    section(`4. Read-only filesystem inspection: ${targetPath}`);

    let metadata;

    try {
        metadata = fs.statSync(targetPath);
    } catch (error) {
        console.log(`Unable to inspect path: ${error.message}`);
        return;
    }

    console.log(`Size: ${metadata.size} bytes`);
    console.log(`Mode: ${modeToSymbolic(metadata.mode & 0o777, metadata.isDirectory())}`);
    console.log(`Raw permission bits: ${(metadata.mode & 0o777).toString(8).padStart(3, '0')}`);
    console.log(`UID: ${metadata.uid}`);
    console.log(`GID: ${metadata.gid}`);
    console.log(`Directory: ${yesNo(metadata.isDirectory())}`);
    console.log(`Regular file: ${yesNo(metadata.isFile())}`);
    console.log(`Symbolic link target: ${metadata.isSymbolicLink() ? 'yes' : 'no'}`);

    console.log('\nNode.js access checks for the current process:');

    for (const [name, mode] of [
        ['read', fs.constants.R_OK],
        ['write', fs.constants.W_OK],
        ['execute', fs.constants.X_OK]
    ]) {
        try {
            fs.accessSync(targetPath, mode);
            console.log(`  ${name}: yes`);
        } catch {
            console.log(`  ${name}: no`);
        }
    }
}

// ---------------------------------------------------------------------------
// 5. Authentication versus authorization
// ---------------------------------------------------------------------------

function explainAuthenticationAuthorization() {
    section('5. Authentication versus authorization');

    console.log('Authentication: establish or verify an identity.');
    console.log('Authorization: decide whether that identity may perform an action.');
    console.log('Privilege management: control acquisition and use of elevated authority.');

    subsection('Application example');

    const users = new Map([
        ['alice', { authenticated: true, roles: new Set(['analyst']) }],
        ['bob', { authenticated: true, roles: new Set(['administrator']) }],
        ['eve', { authenticated: false, roles: new Set() }]
    ]);

    function authorize(username, requiredRole) {
        const account = users.get(username);

        if (!account || !account.authenticated) {
            return false;
        }

        return account.roles.has(requiredRole);
    }

    console.log(`Alice may administer system: ${authorize('alice', 'administrator')}`);
    console.log(`Bob may administer system: ${authorize('bob', 'administrator')}`);
    console.log(`Eve may administer system: ${authorize('eve', 'administrator')}`);
}

// ---------------------------------------------------------------------------
// 6. Application privilege model
// ---------------------------------------------------------------------------

class AuthorizationPolicy {
    constructor() {
        this.permissionsByRole = new Map();
    }

    defineRole(role, permissions) {
        this.permissionsByRole.set(role, new Set(permissions));
    }

    isAllowed(roles, permission) {
        return roles.some(role => {
            const permissions = this.permissionsByRole.get(role);
            return permissions && permissions.has(permission);
        });
    }
}

function demonstrateLeastPrivilege() {
    section('6. Application-level least privilege');

    const policy = new AuthorizationPolicy();

    policy.defineRole('viewer', [
        'report.read'
    ]);

    policy.defineRole('analyst', [
        'report.read',
        'report.export'
    ]);

    policy.defineRole('administrator', [
        'report.read',
        'report.export',
        'user.manage',
        'system.configure'
    ]);

    const accounts = {
        alice: ['viewer'],
        bob: ['analyst'],
        carol: ['administrator']
    };

    for (const [username, roles] of Object.entries(accounts)) {
        console.log(
            `${username}: roles=${roles.join(', ')}, ` +
            `system.configure=${policy.isAllowed(roles, 'system.configure')}`
        );
    }

    console.log(
        '\nThe same least-privilege principle applies to operating-system groups, '
        + 'sudo rules, service accounts, and application roles.'
    );
}

// ---------------------------------------------------------------------------
// 7. Directory access
// ---------------------------------------------------------------------------

function explainDirectoryPermissions() {
    section('7. Directory permissions');

    console.log('For directories:');
    console.log('  r = list directory entries');
    console.log('  w = create/remove/rename entries when combined with appropriate x');
    console.log('  x = traverse/search the directory');

    console.log('\nPath example: /srv/project/data/report.txt');
    console.log(
        'A process needs appropriate traversal permission on parent directories '
        + 'to reach the final object.'
    );
}

// ---------------------------------------------------------------------------
// 8. Special bits
// ---------------------------------------------------------------------------

function explainSpecialBits() {
    section('8. Special permission bits');

    console.log('setuid -> 4xxx');
    console.log('setgid -> 2xxx');
    console.log('sticky -> 1xxx');

    console.log('\nExamples:');
    console.log('4755 -> setuid-style executable permission');
    console.log('2755 -> setgid-style executable permission');
    console.log('1777 -> commonly associated with shared temporary directories');

    console.log(
        '\nSpecial bits require careful security analysis because they can '
        + 'change the effective authority associated with a process or resource.'
    );
}

// ---------------------------------------------------------------------------
// 9. Safe sudo observation
// ---------------------------------------------------------------------------

function inspectSudoPolicy() {
    section('9. sudo policy observation');

    if (process.platform === 'win32') {
        console.log('sudo demonstration skipped because this is not a Unix-like environment.');
        return;
    }

    try {
        const output = execFileSync('sudo', ['-n', '-l'], {
            encoding: 'utf8',
            stdio: ['ignore', 'pipe', 'pipe']
        });

        console.log(output.trim() || 'sudo returned no policy text.');
    } catch (error) {
        console.log(
            'sudo policy could not be queried non-interactively. ' +
            'This is normal when authentication or policy interaction is required.'
        );

        if (error.stderr) {
            console.log(String(error.stderr).trim());
        }
    }
}

// ---------------------------------------------------------------------------
// 10. Group-based authorization simulation
// ---------------------------------------------------------------------------

function demonstrateGroupAuthorization() {
    section('10. Group-based access-control simulation');

    const groupMembership = new Map([
        ['alice', new Set(['developers', 'analytics'])],
        ['bob', new Set(['operations'])],
        ['carol', new Set(['developers', 'security'])]
    ]);

    const resources = [
        { name: 'source-code', requiredGroup: 'developers' },
        { name: 'production-operations', requiredGroup: 'operations' },
        { name: 'security-audit', requiredGroup: 'security' },
        { name: 'public-report', requiredGroup: null }
    ];

    function canUseResource(username, resource) {
        if (!resource.requiredGroup) {
            return true;
        }

        return groupMembership.get(username)?.has(resource.requiredGroup) ?? false;
    }

    for (const username of groupMembership.keys()) {
        console.log(`\n${username}:`);

        for (const resource of resources) {
            console.log(
                `  ${resource.name}: ${yesNo(canUseResource(username, resource))}`
            );
        }
    }
}

// ---------------------------------------------------------------------------
// 11. Edge cases
// ---------------------------------------------------------------------------

function demonstrateEdgeCases() {
    section('11. Permission edge cases');

    const cases = [
        {
            description: 'Owner bits take precedence over group membership',
            identity: new Identity(1000, 999, [100]),
            object: new PermissionObject(1000, 100, 0o040),
            permission: 'READ'
        },
        {
            description: 'Supplementary groups can grant group access',
            identity: new Identity(1001, 200, [100]),
            object: new PermissionObject(1000, 100, 0o640),
            permission: 'READ'
        },
        {
            description: 'Outsider uses other bits',
            identity: new Identity(1001, 200),
            object: new PermissionObject(1000, 100, 0o644),
            permission: 'READ'
        }
    ];

    for (const testCase of cases) {
        console.log(`\n${testCase.description}`);
        console.log(`Selected class: ${selectPermissionClass(testCase.identity, testCase.object)}`);
        console.log(
            `Allowed: ${yesNo(
                canAccess(testCase.identity, testCase.object, testCase.permission)
            )}`
        );
    }
}

// ---------------------------------------------------------------------------
// 12. Tests
// ---------------------------------------------------------------------------

function runTests() {
    section('12. Automated tests');

    const owner = new Identity(1000, 100);
    const groupMember = new Identity(1001, 100);
    const supplementary = new Identity(1002, 200, [100]);
    const outsider = new Identity(1003, 300);

    const object = new PermissionObject(1000, 100, 0o640);

    const tests = [
        ['owner read', () => canAccess(owner, object, 'READ'), true],
        ['owner write', () => canAccess(owner, object, 'WRITE'), true],
        ['owner execute', () => canAccess(owner, object, 'EXECUTE'), false],
        ['group read', () => canAccess(groupMember, object, 'READ'), true],
        ['group write', () => canAccess(groupMember, object, 'WRITE'), false],
        ['supplementary group read', () => canAccess(supplementary, object, 'READ'), true],
        ['outsider read', () => canAccess(outsider, object, 'READ'), false]
    ];

    let passed = 0;

    for (const [name, test, expected] of tests) {
        let actual;

        try {
            actual = test();
        } catch (error) {
            actual = error;
        }

        const success = actual === expected;

        if (success) {
            passed += 1;
        }

        console.log(`${success ? 'PASS' : 'FAIL'} ${name}`);
    }

    console.log(`\n${passed}/${tests.length} tests passed.`);
}

// ---------------------------------------------------------------------------
// 13. Asynchronous filesystem example
// ---------------------------------------------------------------------------

async function asynchronousPermissionInspection(targetPath) {
    section('13. Asynchronous filesystem inspection');

    try {
        const metadata = await fs.promises.stat(targetPath);

        console.log(
            `Asynchronous mode: ${(metadata.mode & 0o777).toString(8).padStart(3, '0')}`
        );

        console.log(
            `Asynchronous owner UID: ${metadata.uid}`
        );

        console.log(
            'The asynchronous API is useful when permission-related filesystem '
            + 'inspection is part of a server handling many concurrent requests.'
        );
    } catch (error) {
        console.log(`Inspection failed: ${error.message}`);
    }
}

// ---------------------------------------------------------------------------
// 14. Security checklist
// ---------------------------------------------------------------------------

function securityChecklist() {
    section('14. Security checklist');

    const checks = [
        'Use dedicated service identities.',
        'Minimize supplementary group membership.',
        'Avoid unnecessary world-writable files and directories.',
        'Use narrow sudo rules instead of unrestricted privilege.',
        'Protect authentication secrets.',
        'Review privileged executable files.',
        'Audit changes to users, groups, and authorization policy.',
        'Use application roles independently from operating-system permissions.',
        'Consider ACLs when owner/group/other is insufficient.',
        'Use capabilities or sandboxing where appropriate.',
        'Treat authentication and authorization as separate controls.',
        'Revalidate authorization for sensitive operations.'
    ];

    checks.forEach((check, index) => {
        console.log(`${index + 1}. ${check}`);
    });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
    const targetPath = process.argv[2] || __filename;

    demonstrateProcessIdentity();
    demonstratePermissionModel();
    demonstrateModesAndUmask();
    inspectFilesystemObject(path.resolve(targetPath));
    explainAuthenticationAuthorization();
    demonstrateLeastPrivilege();
    explainDirectoryPermissions();
    explainSpecialBits();
    inspectSudoPolicy();
    demonstrateGroupAuthorization();
    demonstrateEdgeCases();
    runTests();
    await asynchronousPermissionInspection(path.resolve(targetPath));
    securityChecklist();

    section('Educational boundary');
    console.log(
        'This program performs observation and in-memory simulation only. '
        + 'It does not create accounts, modify groups, change passwords, '
        + 'change ownership, or change filesystem permissions.'
    );
}

main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exitCode = 1;
});
