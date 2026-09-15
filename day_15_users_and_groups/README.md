# Users and groups: permissions, authentication, and privilege management

## Topic introduction

Linux security begins with identity. A process normally operates with a user identity represented by a user ID, or UID, and one or more group identities represented by group IDs, or GIDs. The operating system uses these identities when making authorization decisions for files, directories, devices, processes, and other protected resources.

The traditional Unix security model separates subjects into three permission classes: owner, group, and other. Each class can receive read, write, and execute permissions. Linux systems build on this model with supplementary groups, sudo, ACLs, capabilities, namespaces, and mandatory access-control systems such as SELinux and AppArmor.

This project studies the subject from the basic account model through more advanced privilege-management concepts. The Python implementation provides a detailed educational exploration of Linux identity and permission behavior. The JavaScript implementation complements it with portable simulations, Node.js process information, asynchronous filesystem inspection, and application-level authorization. The C++ implementation models a realistic document repository in which operating-system-style permissions interact with application roles and administrative privileges.

## Fundamental concepts

### Users

A user account represents an identity that can be associated with processes and resources. Linux identifies users internally through numeric UIDs.

A typical account has several attributes:

- username
- UID
- primary GID
- home directory
- login shell
- account metadata
- authentication configuration

The Python program reads the system password database through Python's `pwd` module. On Linux, this information commonly corresponds to `/etc/passwd`, although the operating system can obtain account information through other sources such as LDAP, NIS, or system configuration mechanisms.

A traditional `/etc/passwd` entry contains seven fields:

1. username
2. password placeholder
3. UID
4. primary GID
5. GECOS or descriptive information
6. home directory
7. login shell

Modern Linux systems normally keep password hashes in `/etc/shadow` rather than directly exposing them through `/etc/passwd`.

### Groups

A group is an identity collection represented by a GID. Groups are particularly useful when several users need access to the same resources.

A user has a primary group and may also have supplementary groups. The Python program obtains supplementary group IDs through `os.getgroups()` and resolves group information using Python's `grp` module.

Group membership is important because a user's supplementary groups can affect file authorization even when the group is not the user's primary group.

### UID and GID

A UID identifies a user to the operating system. A GID identifies a group.

UID and GID values are numeric internally, while usernames and group names are human-readable representations.

UID 0 conventionally represents the root superuser identity. Root is historically associated with broad administrative authority, although modern Linux security mechanisms can restrict or divide privileged operations.

## Authentication and authorization

Authentication and authorization are different concepts.

Authentication establishes or verifies identity. Examples include passwords, SSH keys, hardware-backed credentials, and multi-factor authentication.

Authorization determines what an authenticated identity may do. Examples include Unix permissions, group membership, sudo policies, ACLs, application roles, and mandatory access-control policies.

Privilege management concerns controlled access to additional authority. `sudo` is a common Linux mechanism for allowing authorized users to execute selected commands with elevated privileges.

A user who successfully authenticates is not automatically authorized to perform every operation.

## File ownership

A regular Unix-like file normally has:

- an owning UID
- an owning GID
- permission bits

For example, a conceptual file might have:

`owner UID = 1000`

`group GID = 100`

`mode = 0640`

The `0640` permission mode means:

- owner: read and write
- group: read
- other: no permissions

The symbolic representation is `rw-r-----`.

Ownership and permissions are separate concepts. Changing ownership changes which identity is considered the owner or owning group. Changing permission bits changes what the applicable identity classes are allowed to do.

## Read, write, and execute permissions

The traditional permission values are:

- read = 4
- write = 2
- execute = 1

The three values are combined for each permission class.

Common examples include:

- `600` = `rw-------`
- `640` = `rw-r-----`
- `644` = `rw-r--r--`
- `700` = `rwx------`
- `750` = `rwxr-x---`
- `755` = `rwxr-xr-x`

For ordinary files, read generally permits reading content, write permits modification, and execute permits execution when other operating-system conditions allow it.

Directory permissions have different practical meanings.

For a directory:

- read permits listing directory entries
- write permits creating, removing, or renaming entries when the necessary traversal permissions are also available
- execute permits traversal or searching through the directory

This distinction is important. A user can have read permission on a file while still being unable to reach it because the user lacks execute permission on a parent directory.

## How permission selection works

Traditional Unix permission evaluation can be represented as:

1. Check whether the process UID matches the resource owner UID.
2. If it does, evaluate the owner permission bits.
3. Otherwise, determine whether the user belongs to the owning group.
4. If so, evaluate the group permission bits.
5. Otherwise, evaluate the other permission bits.

The permission classes are not normally combined.

This is demonstrated by the permission evaluators in all three implementations.

The Python program uses the `Identity`, `PermissionObject`, `permission_class`, and `has_permission` abstractions.

The JavaScript program provides equivalent `Identity` and `PermissionObject` classes, but expresses the logic using JavaScript classes, `Map`, `Set`, and functions.

The C++ case study incorporates the same logic inside the `Repository` class and applies it to documents.

## Numeric and symbolic permission notation

Numeric permissions use octal notation because each permission class occupies three bits.

For example:

`0640`

can be divided into:

- `6` for owner
- `4` for group
- `0` for other

The owner value `6` is read plus write:

`4 + 2 = 6`

The group value `4` is read only.

The other value `0` provides no access.

The Python implementation demonstrates symbolic conversion with `stat.filemode`. The JavaScript implementation provides its own `modeToSymbolic` function. The C++ program implements a similar conversion for the case study.

## chmod

`chmod` changes permission bits on a filesystem object.

Examples of common conceptual operations include:

`chmod 600 file`

`chmod 640 file`

`chmod 755 executable`

The numeric notation is compact, while symbolic notation can express individual changes more precisely.

The project does not automatically execute permission-changing commands. This is intentional because changing permissions on the host system is an administrative operation rather than a safe educational default.

## umask

The umask influences the permissions assigned during creation of files and directories.

A simplified model is:

`resulting mode = requested mode AND NOT umask`

A commonly requested regular-file mode is `0666`, while a directory commonly starts from `0777` before masking.

For a umask of `0022`:

`0666 & ~0022` produces `0644`

For a directory:

`0777 & ~0022` produces `0755`

The actual result can also be affected by the application creating the object, the filesystem, default ACLs, and other operating-system behavior.

The Python and JavaScript implementations demonstrate this calculation without modifying the process umask.

## Special permission bits

Unix-like systems provide special permission bits beyond ordinary read, write, and execute bits.

### setuid

The setuid bit on an executable can cause execution to occur with the file owner's effective identity, subject to operating-system rules and security restrictions.

The conventional numeric prefix is `4`.

Example:

`4755`

Setuid executables must be treated carefully because they can create privilege boundaries between the invoking user and the executable's owner.

### setgid

The setgid bit has multiple effects.

On an executable, it can cause execution to use the file's group identity in the appropriate context.

On a directory, setgid commonly causes newly created objects to inherit the directory's group, which is useful for collaborative directories.

The conventional numeric prefix is `2`.

Example:

`2755`

### Sticky bit

The sticky bit is especially important on shared directories.

A directory such as a temporary shared directory may permit many users to create files while restricting users from deleting or renaming files owned by other users, subject to the operating system's authorization rules.

The conventional numeric prefix is `1`.

Example:

`1777`

The Python implementation describes and demonstrates these special modes.

## ACLs

Traditional owner/group/other permissions are intentionally simple. They become less convenient when different individual users need different permissions on the same resource.

POSIX ACLs extend the traditional model with entries for named users and groups.

The Python program checks whether `getfacl` and `setfacl` are available and demonstrates read-only ACL inspection when possible.

ACLs introduce additional complexity. The ACL mask is particularly important because it can constrain effective permissions for named users, named groups, and the owning group entry.

A production authorization review should therefore not assume that the three traditional mode classes completely describe access.

## Sudo and privilege elevation

`sudo` allows an authorized user to execute selected commands with elevated privileges.

A secure sudo configuration follows least privilege.

Instead of granting unrestricted administrative access, an organization can restrict:

- which users may elevate
- which commands they may execute
- which target identities they may use
- under what conditions elevation is allowed

The Python and JavaScript programs only attempt safe, non-interactive policy observation. They do not automatically invoke privileged commands.

A failed non-interactive sudo query does not necessarily indicate that sudo is absent or broken. Authentication may require an interactive password, or the policy may prohibit the requested operation.

## Authentication mechanisms

Authentication can use different factors and protocols.

Common examples include:

- passwords
- SSH public keys
- certificates
- hardware-backed credentials
- multi-factor authentication
- centralized directory services

Password authentication requires secure password storage. Password hashes should not be stored in ordinary readable account metadata.

SSH key authentication allows a private key to remain with the user while the server stores the corresponding public key.

Centralized identity systems can make enterprise user and group management easier, but they also introduce dependencies on directory availability, synchronization, configuration, and network security.

## Account lifecycle

A secure account-management process generally includes:

- provisioning
- configuration
- controlled use
- auditing
- modification
- disabling
- retirement

The Python implementation presents these stages and references standard Linux account-management utilities such as `useradd`, `usermod`, `userdel`, `groupadd`, `groupmod`, `groupdel`, and `passwd`.

The programs intentionally do not execute these operations automatically because account management changes the security state of the host.

## Service accounts

Service accounts provide identities for applications and system services.

A service should generally receive only the authority required for its function.

For example, a web service that only needs to read application data should not normally run with unrestricted administrator privileges.

A separate service identity improves:

- isolation
- auditing
- ownership clarity
- incident investigation
- privilege reduction

Service identities should also be reviewed when applications are retired or replaced.

## Least privilege

Least privilege means granting only the authority required for a task.

The principle applies at several levels:

- user group membership
- file permissions
- sudo rules
- service account privileges
- application roles
- database privileges
- Linux capabilities
- container permissions

The JavaScript implementation demonstrates this at the application level with an `AuthorizationPolicy` class.

A viewer receives `report.read`.

An analyst receives `report.read` and `report.export`.

An administrator receives additional management privileges.

This illustrates a broader security principle: authorization should be explicit rather than assumed.

## Python implementation

The Python script is primarily an operating-system study and diagnostic program.

It demonstrates:

- current UID and GID information
- supplementary groups
- the passwd database
- the group database
- user and service-account concepts
- permission-bit notation
- real filesystem metadata
- owner/group/other evaluation
- directory permissions
- special permission bits
- umask calculations
- sudo policy inspection
- ACL availability
- account lifecycle concepts
- common security mistakes
- advanced privilege concepts
- permission tests
- a small read-only security audit

The `Identity` class represents an abstract process identity. It contains a UID, primary GID, and supplementary GIDs.

The `PermissionObject` class represents an object controlled by Unix-style permissions.

The `permission_class` function determines whether owner, group, or other permissions apply.

The `has_permission` function then evaluates a requested read, write, or execute operation.

This separation is useful because it allows permission logic to be tested without changing the host operating system.

## JavaScript implementation

The JavaScript implementation complements the Python program rather than attempting to reproduce every Linux-specific interface.

Node.js provides useful operating-system and filesystem functionality through modules such as `process` and `fs`.

The program demonstrates:

- process UID and GID information where exposed by the platform
- supplementary groups where supported
- filesystem metadata
- filesystem access checks
- asynchronous filesystem inspection
- Unix-like permission simulation
- group-based application authorization
- application roles
- least privilege
- special permission concepts
- safe sudo observation
- automated tests

JavaScript's `Map` and `Set` structures are particularly appropriate for modeling group membership and role membership.

The asynchronous example uses `fs.promises.stat`. This matters for server-side JavaScript because filesystem operations can be integrated into applications without unnecessarily blocking the event loop.

The JavaScript implementation therefore connects low-level identity concepts with common application-level authorization patterns.

## C++ case study

### Problem being solved

The C++ program models a secure document repository used by an organization.

The repository contains documents owned by users and groups. Users have primary and supplementary groups and application roles.

The system must determine whether a user may:

- create a document
- read a document
- modify a document
- change document permissions
- change group ownership
- disable another account

Every sensitive action is recorded in an audit log.

### Users and groups

The `User` structure contains:

- UID
- username
- primary GID
- supplementary groups
- application roles
- account state

The `Group` structure contains:

- GID
- group name
- member UIDs

The `belongsTo` method checks both primary and supplementary group membership.

This reflects an important distinction between primary and supplementary group membership.

### Documents

The `Document` structure contains:

- document ID
- name
- owner UID
- owning GID
- permission mode
- contents
- confidentiality flag

The permission mode uses Unix-style owner/group/other bits.

### Permission evaluation

The `Repository` class uses `selectAccessClass` to determine which permission class applies.

The decision follows the conventional sequence:

1. owner
2. owning group
3. other

The `hasPermission` method then checks the corresponding bit.

This design keeps permission evaluation centralized instead of duplicating authorization logic throughout the application.

### Application authorization

The C++ case study demonstrates an important real-world distinction.

Operating-system permissions and application authorization are related but are not identical.

A document repository may impose additional rules such as confidentiality, role requirements, workflow restrictions, or account status.

The program therefore maintains application roles such as:

- viewer
- editor
- security administrator
- system administrator

The repository checks these roles for administrative operations.

### Account state

An account has an `active` flag.

When an administrator disables an account, subsequent operations are rejected even if the document's ordinary permission bits would otherwise permit access.

This demonstrates why identity state and resource permissions are separate authorization inputs.

### Administrative operations

Changing permission modes is treated as a sensitive action.

The case study allows the resource owner or an appropriately privileged administrator to change the mode.

Changing the owning group requires administrative authority.

Disabling accounts requires administrative authority.

These rules demonstrate least privilege and explicit administrative boundaries.

### Audit logging

The `AuditLog` class records:

- username
- action
- resource
- whether the operation was allowed
- reason

Security logs are important because authorization is not only about preventing unauthorized operations. Organizations also need to understand attempted and successful privileged actions.

In production systems, audit records should normally include timestamps, request identifiers, source information, authentication context, and enough structured information to support investigation.

## Important distinctions

### Primary group versus supplementary group

A primary group is the user's principal group association.

Supplementary groups provide additional memberships.

A user can therefore be primarily associated with one group while receiving access through another group.

### Authentication versus authorization

Authentication establishes identity.

Authorization determines permitted actions.

These processes should not be treated as interchangeable.

### Ownership versus permission

Ownership determines which UID and GID are associated with a resource.

Permissions determine what the applicable identity class may do.

Changing ownership and changing permission bits are different operations.

### Operating-system authorization versus application authorization

Operating-system permissions protect operating-system resources.

Applications frequently implement their own roles and authorization rules.

A secure application should not assume that filesystem ownership alone expresses every business-level authorization requirement.

### sudo versus ordinary file permissions

File permissions govern access to resources.

Sudo governs controlled execution of commands under an elevated identity.

They solve different problems but may interact in a system's overall privilege model.

## Edge cases

Several details can produce unexpected authorization results.

### Owner precedence

If the process UID matches the resource owner UID, owner permissions apply. Group permissions are not simply added to the owner permissions.

### Supplementary groups

A user may gain group access through a supplementary group even though that group is not the primary group.

### Directory traversal

A readable file can still be unreachable if a parent directory lacks appropriate traversal permission.

### Special bits

setuid, setgid, and sticky-bit behavior cannot be reduced to ordinary read, write, and execute permissions.

### ACLs

An ACL can provide additional authorization information that is not obvious from a simple three-digit mode value.

### Capabilities

Modern Linux can divide privileged operations into capabilities rather than relying exclusively on a single all-powerful superuser model.

### Mandatory access control

SELinux and AppArmor can impose restrictions beyond traditional discretionary access control.

### Containers

Containers can change how UIDs, GIDs, namespaces, capabilities, and filesystem views are perceived by a process.

### Network filesystems

Remote filesystems can have authorization semantics that differ from a simple local filesystem model.

## Common mistakes

### Using 777 as a default solution

`777` grants read, write, and execute permissions to owner, group, and other.

It can create unnecessary exposure and should not be used as a generic troubleshooting solution.

### Excessive sudo privileges

Giving broad administrator privileges for a narrow task increases the consequences of compromised credentials or accidental commands.

### Unnecessary group membership

Every additional group can potentially expand access.

Group membership should be reviewed as responsibilities change.

### Running services with excessive privileges

A vulnerable service can expose the authority of its process identity.

Dedicated, restricted service accounts reduce the potential impact.

### Confusing login access with resource access

A successful login does not imply access to every file, directory, process, or administrative operation.

### Ignoring directory permissions

Checking only the final file's permission bits can lead to incorrect conclusions about actual path accessibility.

### Treating permissions as the complete security model

Real systems may also use ACLs, capabilities, SELinux, AppArmor, namespaces, seccomp, container isolation, application roles, and external identity providers.

## Limitations of the educational implementations

The Python and JavaScript permission evaluators intentionally model the traditional owner/group/other mechanism rather than implementing every Linux authorization rule.

The C++ repository is a simulation rather than a real filesystem-backed service.

The implementations do not modify system accounts, passwords, group membership, ownership, or permissions.

They do not implement a complete PAM authentication stack, `/etc/shadow` password verification, LDAP, Kerberos, SELinux policy evaluation, AppArmor policy evaluation, Linux capabilities, namespaces, or POSIX ACL evaluation.

These limitations are deliberate. The goal is to make the fundamental identity and authorization mechanisms explicit before introducing the additional layers used by production Linux systems.

## Performance considerations

Permission checks occur frequently in operating systems, so the basic Unix permission model is intentionally compact.

The simulations use efficient structures for their respective languages.

The Python implementation uses sets for supplementary group membership.

The JavaScript implementation uses `Set` and `Map` for group and role lookups.

The C++ implementation uses `std::set` and `std::unordered_map`.

For small collections, these structures are more than sufficient. Larger systems require careful consideration of lookup complexity, cache behavior, synchronization, identity-directory latency, and authorization-policy evaluation.

The C++ repository centralizes permission checks so authorization rules do not become duplicated across many operations. Centralization reduces inconsistent policy decisions and makes testing easier.

## Security considerations

Security-sensitive implementations should apply least privilege throughout the system.

Important controls include:

- minimizing group membership
- restricting sudo access
- using dedicated service identities
- protecting authentication secrets
- auditing privileged actions
- disabling unused accounts
- reviewing ownership and permissions
- avoiding unnecessary world-writable resources
- separating authentication from authorization
- applying application-level authorization where needed
- using stronger isolation mechanisms when traditional permissions are insufficient

Security controls should be layered. A secure system should not depend on a single permission bit or a single authorization mechanism.

## Advanced privilege management

### Linux capabilities

Linux capabilities divide certain traditionally privileged operations into distinct privileges.

Examples include capabilities associated with:

- changing ownership
- network administration
- binding to privileged ports
- overriding selected discretionary access checks
- changing user IDs

Capabilities can reduce the need for an application to run with unrestricted administrator authority.

### Namespaces

Linux namespaces isolate views of system resources.

They are fundamental to many container technologies and can isolate aspects such as:

- process IDs
- network interfaces
- mount points
- user and group IDs

### seccomp

seccomp can restrict the system calls a process is allowed to make.

This can reduce the attack surface of a process even when ordinary file permissions alone are insufficient.

### SELinux and AppArmor

SELinux and AppArmor provide mandatory access-control mechanisms.

They can impose policies that restrict processes beyond traditional discretionary Unix permissions.

The distinction is important:

Discretionary access control is strongly influenced by resource ownership and user-controlled permissions.

Mandatory access control applies centrally defined security policy that can constrain otherwise permitted operations.

## Implementation considerations

The three languages emphasize different aspects of the subject.

Python is particularly effective for system inspection, rapid experimentation, readable permission simulations, and scripting administrative analysis.

JavaScript is useful for connecting identity and permission concepts to application authorization, server-side programming, asynchronous filesystem APIs, maps, sets, and role-based access control.

C++ is useful for demonstrating explicit data modeling, strong type distinctions, deterministic control over data structures, modular authorization logic, and performance-oriented system design.

The core security principles remain language-independent.

## Real-world relevance

User and group management is foundational to Linux administration, cloud infrastructure, enterprise systems, DevOps, containers, security engineering, and application deployment.

The same principles appear in many environments:

- Linux servers
- cloud virtual machines
- container platforms
- CI/CD systems
- databases
- web servers
- application backends
- shared development environments
- enterprise identity systems
- security operations

A production system normally combines several layers rather than relying solely on traditional Unix mode bits.

A typical security architecture may contain:

identity provider → authentication → operating-system identity → groups → filesystem permissions and ACLs → process privileges → application authorization → audit logging

Understanding the relationships between these layers is essential for diagnosing access failures and designing systems that provide necessary access without granting unnecessary authority.
