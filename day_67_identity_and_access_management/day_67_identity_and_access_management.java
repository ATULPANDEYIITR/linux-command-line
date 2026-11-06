import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Enterprise Identity and Access Management.
 *
 * Java 17 implementation covering:
 * - Identity lifecycle
 * - Group-based role assignment
 * - Role-based access control
 * - Policy evaluation
 * - Explicit deny precedence
 * - Temporary access approval
 * - Least privilege reporting
 * - Immutable audit records
 *
 * Compile: javac IAMApplication.java
 * Run: java IAMApplication
 */
public class IAMApplication {

    enum AccountStatus {
        ACTIVE,
        DISABLED,
        LOCKED
    }

    enum PolicyEffect {
        ALLOW,
        DENY
    }

    enum RequestStatus {
        PENDING,
        APPROVED,
        REJECTED,
        EXPIRED
    }

    enum AuditDecision {
        ALLOW,
        DENY
    }

    static class IAMException extends RuntimeException {
        IAMException(String message) {
            super(message);
        }
    }

    static class ValidationException extends IAMException {
        ValidationException(String message) {
            super(message);
        }
    }

    static class NotFoundException extends IAMException {
        NotFoundException(String message) {
            super(message);
        }
    }

    static class AuthorizationException extends IAMException {
        AuthorizationException(String message) {
            super(message);
        }
    }

    static class DuplicateException extends IAMException {
        DuplicateException(String message) {
            super(message);
        }
    }

    record Permission(String resource, String action) {
        Permission {
            if (resource == null || resource.isBlank()) {
                throw new ValidationException(
                    "Resource cannot be empty."
                );
            }

            if (action == null || action.isBlank()) {
                throw new ValidationException(
                    "Action cannot be empty."
                );
            }

            resource = resource.toLowerCase().trim();
            action = action.toLowerCase().trim();
        }
    }

    static final class User {
        private final String id;
        private final String username;
        private final String email;
        private final String department;
        private final Instant createdAt;

        private final Set<String> groupIds = new HashSet<>();

        private AccountStatus status = AccountStatus.ACTIVE;
        private long version = 1;

        User(
            String id,
            String username,
            String email,
            String department
        ) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("User ID required.");
            }

            if (username == null || username.isBlank()) {
                throw new ValidationException("Username required.");
            }

            if (
                email == null ||
                !email.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$")
            ) {
                throw new ValidationException("Invalid email.");
            }

            if (department == null || department.isBlank()) {
                throw new ValidationException("Department required.");
            }

            this.id = id;
            this.username = username.trim();
            this.email = email.toLowerCase();
            this.department = department.trim();
            this.createdAt = Instant.now();
        }

        String id() {
            return id;
        }

        String username() {
            return username;
        }

        String email() {
            return email;
        }

        String department() {
            return department;
        }

        AccountStatus status() {
            return status;
        }

        Set<String> groupIds() {
            return Collections.unmodifiableSet(groupIds);
        }

        long version() {
            return version;
        }
    }

    static final class Role {
        private final String id;
        private final String name;
        private final String description;
        private final Set<Permission> permissions;

        Role(
            String id,
            String name,
            String description,
            Set<Permission> permissions
        ) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Role ID required.");
            }

            if (name == null || name.isBlank()) {
                throw new ValidationException("Role name required.");
            }

            this.id = id;
            this.name = name;
            this.description = description;
            this.permissions = Set.copyOf(permissions);
        }

        String id() {
            return id;
        }

        Set<Permission> permissions() {
            return permissions;
        }

        String name() {
            return name;
        }
    }

    static final class Group {
        private final String id;
        private final String name;
        private final Set<String> members = new HashSet<>();
        private final Set<String> roles = new HashSet<>();

        Group(String id, String name) {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Group ID required.");
            }

            if (name == null || name.isBlank()) {
                throw new ValidationException("Group name required.");
            }

            this.id = id;
            this.name = name;
        }
    }

    record Policy(
        String id,
        String name,
        PolicyEffect effect,
        Set<Permission> permissions,
        Set<String> departments,
        Set<String> excludedUsers
    ) {
        Policy {
            if (id == null || id.isBlank()) {
                throw new ValidationException("Policy ID required.");
            }

            if (name == null || name.isBlank()) {
                throw new ValidationException("Policy name required.");
            }

            Objects.requireNonNull(effect);
            permissions = Set.copyOf(permissions);
            departments = Set.copyOf(departments);
            excludedUsers = Set.copyOf(excludedUsers);

            if (permissions.isEmpty()) {
                throw new ValidationException(
                    "Policy requires permissions."
                );
            }
        }
    }

    record AccessRequest(
        String id,
        String userId,
        String approverId,
        Permission permission,
        Instant requestedAt,
        Instant expiresAt,
        RequestStatus status
    ) {}

    record AuditEvent(
        String id,
        Instant timestamp,
        String userId,
        Permission permission,
        AuditDecision decision,
        String reason
    ) {}

    record AccessResult(
        boolean allowed,
        String reason
    ) {}

    record LeastPrivilegeReport(
        String username,
        AccountStatus status,
        Set<String> groups,
        Set<String> roles,
        Set<Permission> permissions
    ) {}

    interface AccessEvaluator {
        AccessResult evaluate(
            User user,
            Permission permission,
            Set<Permission> rolePermissions,
            List<Policy> policies
        );
    }

    static final class DefaultAccessEvaluator
        implements AccessEvaluator {

        @Override
        public AccessResult evaluate(
            User user,
            Permission permission,
            Set<Permission> rolePermissions,
            List<Policy> policies
        ) {
            if (user.status() != AccountStatus.ACTIVE) {
                return new AccessResult(
                    false,
                    "Account is not active."
                );
            }

            List<Policy> applicable = policies.stream()
                .filter(p -> p.permissions().contains(permission))
                .filter(p ->
                    p.departments().isEmpty() ||
                    p.departments().contains(user.department())
                )
                .filter(p -> !p.excludedUsers().contains(user.id()))
                .toList();

            // Explicit deny has priority over every allow.
            var deny = applicable.stream()
                .filter(p -> p.effect() == PolicyEffect.DENY)
                .findFirst();

            if (deny.isPresent()) {
                return new AccessResult(
                    false,
                    "Explicit deny: " + deny.get().name()
                );
            }

            var allow = applicable.stream()
                .filter(p -> p.effect() == PolicyEffect.ALLOW)
                .findFirst();

            if (allow.isPresent()) {
                return new AccessResult(
                    true,
                    "Policy allow: " + allow.get().name()
                );
            }

            if (rolePermissions.contains(permission)) {
                return new AccessResult(
                    true,
                    "Permission assigned through role."
                );
            }

            return new AccessResult(
                false,
                "No matching permission."
            );
        }
    }

    static final class IAMService {
        private final Map<String, User> users = new HashMap<>();
        private final Map<String, Role> roles = new HashMap<>();
        private final Map<String, Group> groups = new HashMap<>();
        private final Map<String, Policy> policies = new HashMap<>();

        private final Map<String, AccessRequest> requests =
            new HashMap<>();

        private final List<AuditEvent> auditEvents =
            new ArrayList<>();

        private final AccessEvaluator evaluator =
            new DefaultAccessEvaluator();

        public void registerUser(User user) {
            if (users.containsKey(user.id())) {
                throw new DuplicateException("Duplicate user ID.");
            }

            boolean duplicate = users.values().stream().anyMatch(
                existing ->
                    existing.email().equalsIgnoreCase(user.email()) ||
                    existing.username().equalsIgnoreCase(user.username())
            );

            if (duplicate) {
                throw new DuplicateException(
                    "Username or email already exists."
                );
            }

            users.put(user.id(), user);
        }

        public void registerRole(Role role) {
            if (roles.putIfAbsent(role.id(), role) != null) {
                throw new DuplicateException("Duplicate role.");
            }
        }

        public void registerGroup(Group group) {
            if (groups.putIfAbsent(group.id, group) != null) {
                throw new DuplicateException("Duplicate group.");
            }
        }

        public void registerPolicy(Policy policy) {
            if (policies.putIfAbsent(policy.id(), policy) != null) {
                throw new DuplicateException("Duplicate policy.");
            }
        }

        private User user(String id) {
            User result = users.get(id);

            if (result == null) {
                throw new NotFoundException(
                    "User not found: " + id
                );
            }

            return result;
        }

        private Group group(String id) {
            Group result = groups.get(id);

            if (result == null) {
                throw new NotFoundException(
                    "Group not found: " + id
                );
            }

            return result;
        }

        private Role role(String id) {
            Role result = roles.get(id);

            if (result == null) {
                throw new NotFoundException(
                    "Role not found: " + id
                );
            }

            return result;
        }

        public void addMember(String userId, String groupId) {
            User user = user(userId);
            Group group = group(groupId);

            user.groupIds.add(groupId);
            group.members.add(userId);
            user.version++;
        }

        public void removeMember(String userId, String groupId) {
            User user = user(userId);
            Group group = group(groupId);

            user.groupIds.remove(groupId);
            group.members.remove(userId);
            user.version++;
        }

        public void assignRole(String groupId, String roleId) {
            Group group = group(groupId);
            role(roleId);

            group.roles.add(roleId);
        }

        public Set<String> effectiveRoles(String userId) {
            User user = user(userId);

            return user.groupIds.stream()
                .map(this::group)
                .flatMap(g -> g.roles.stream())
                .collect(Collectors.toUnmodifiableSet());
        }

        public Set<Permission> effectivePermissions(
            String userId
        ) {
            return effectiveRoles(userId).stream()
                .map(this::role)
                .flatMap(r -> r.permissions().stream())
                .collect(Collectors.toUnmodifiableSet());
        }

        public AccessResult evaluate(
            String userId,
            String resource,
            String action
        ) {
            User user = user(userId);

            Permission permission = new Permission(
                resource,
                action
            );

            return evaluator.evaluate(
                user,
                permission,
                effectivePermissions(userId),
                List.copyOf(policies.values())
            );
        }

        public boolean authorize(
            String userId,
            String resource,
            String action
        ) {
            Permission permission = new Permission(
                resource,
                action
            );

            AccessResult result = evaluate(
                userId,
                resource,
                action
            );

            auditEvents.add(
                new AuditEvent(
                    UUID.randomUUID().toString(),
                    Instant.now(),
                    userId,
                    permission,
                    result.allowed()
                        ? AuditDecision.ALLOW
                        : AuditDecision.DENY,
                    result.reason()
                )
            );

            return result.allowed();
        }

        public void requireAccess(
            String userId,
            String resource,
            String action
        ) {
            if (!authorize(userId, resource, action)) {
                throw new AuthorizationException(
                    "Access denied: " + userId +
                    " cannot " + action + " " + resource
                );
            }
        }

        public void updateStatus(
            String userId,
            AccountStatus status
        ) {
            User user = user(userId);
            user.status = Objects.requireNonNull(status);
            user.version++;
        }

        public void revokeAllAccess(String userId) {
            User user = user(userId);

            for (String groupId :
                 new HashSet<>(user.groupIds)) {
                group(groupId).members.remove(userId);
            }

            user.groupIds.clear();
            user.status = AccountStatus.DISABLED;
            user.version++;
        }

        public AccessRequest requestTemporaryAccess(
            String userId,
            String approverId,
            String resource,
            String action,
            long durationMinutes
        ) {
            User requester = user(userId);
            User approver = user(approverId);

            if (requester.status() != AccountStatus.ACTIVE) {
                throw new AuthorizationException(
                    "Requester is inactive."
                );
            }

            if (approver.status() != AccountStatus.ACTIVE) {
                throw new AuthorizationException(
                    "Approver is inactive."
                );
            }

            if (userId.equals(approverId)) {
                throw new AuthorizationException(
                    "Self-approval is prohibited."
                );
            }

            if (
                durationMinutes < 1 ||
                durationMinutes > 480
            ) {
                throw new ValidationException(
                    "Duration must be between 1 and 480 minutes."
                );
            }

            AccessRequest request = new AccessRequest(
                UUID.randomUUID().toString(),
                userId,
                approverId,
                new Permission(resource, action),
                Instant.now(),
                null,
                RequestStatus.PENDING
            );

            requests.put(request.id(), request);
            return request;
        }

        public AccessRequest approveTemporaryAccess(
            String requestId,
            String approverId,
            long durationMinutes
        ) {
            AccessRequest request = requests.get(requestId);

            if (request == null) {
                throw new NotFoundException(
                    "Access request not found."
                );
            }

            if (request.status() != RequestStatus.PENDING) {
                throw new IAMException(
                    "Request is not pending."
                );
            }

            if (!request.approverId().equals(approverId)) {
                throw new AuthorizationException(
                    "Incorrect approver."
                );
            }

            User approver = user(approverId);

            if (approver.status() != AccountStatus.ACTIVE) {
                throw new AuthorizationException(
                    "Approver is inactive."
                );
            }

            if (durationMinutes < 1 || durationMinutes > 480) {
                throw new ValidationException("Invalid duration.");
            }

            AccessRequest approved = new AccessRequest(
                request.id(),
                request.userId(),
                request.approverId(),
                request.permission(),
                request.requestedAt(),
                Instant.now().plus(
                    durationMinutes,
                    ChronoUnit.MINUTES
                ),
                RequestStatus.APPROVED
            );

            requests.put(requestId, approved);
            return approved;
        }

        public LeastPrivilegeReport report(String userId) {
            User user = user(userId);

            return new LeastPrivilegeReport(
                user.username(),
                user.status(),
                Set.copyOf(user.groupIds),
                effectiveRoles(userId),
                effectivePermissions(userId)
            );
        }

        public List<AuditEvent> auditReport() {
            return List.copyOf(auditEvents);
        }

        public long countDeniedEvents() {
            return auditEvents.stream()
                .filter(e -> e.decision() == AuditDecision.DENY)
                .count();
        }
    }

    private static Permission permission(
        String resource,
        String action
    ) {
        return new Permission(resource, action);
    }

    public static void main(String[] args) {
        IAMService iam = new IAMService();

        User alice = new User(
            "U001",
            "alice",
            "alice@example.com",
            "Finance"
        );

        User bob = new User(
            "U002",
            "bob",
            "bob@example.com",
            "Engineering"
        );

        User carol = new User(
            "U003",
            "carol",
            "carol@example.com",
            "Security"
        );

        iam.registerUser(alice);
        iam.registerUser(bob);
        iam.registerUser(carol);

        Role reportReader = new Role(
            "R001",
            "ReportReader",
            "Read business reports",
            Set.of(permission("reports", "read"))
        );

        Role securityAdmin = new Role(
            "R002",
            "SecurityAdministrator",
            "Manage identity records",
            Set.of(
                permission("users", "manage"),
                permission("users", "delete")
            )
        );

        iam.registerRole(reportReader);
        iam.registerRole(securityAdmin);

        iam.registerGroup(new Group("G001", "Finance"));
        iam.registerGroup(new Group("G002", "Engineering"));
        iam.registerGroup(new Group("G003", "Security"));

        iam.assignRole("G001", "R001");
        iam.assignRole("G002", "R001");
        iam.assignRole("G003", "R002");

        iam.addMember("U001", "G001");
        iam.addMember("U002", "G002");
        iam.addMember("U003", "G003");

        iam.registerPolicy(
            new Policy(
                "P001",
                "PayrollProtection",
                PolicyEffect.DENY,
                Set.of(permission("payroll", "read")),
                Set.of("Finance"),
                Set.of()
            )
        );

        iam.registerPolicy(
            new Policy(
                "P002",
                "FinanceReportCreation",
                PolicyEffect.ALLOW,
                Set.of(permission("reports", "create")),
                Set.of("Finance"),
                Set.of()
            )
        );

        System.out.println("IDENTITY AND ACCESS MANAGEMENT");
        System.out.println("================================");

        String[][] checks = {
            {"U001", "reports", "read"},
            {"U001", "reports", "create"},
            {"U001", "payroll", "read"},
            {"U002", "reports", "create"},
            {"U003", "users", "delete"}
        };

        for (String[] check : checks) {
            AccessResult result = iam.evaluate(
                check[0],
                check[1],
                check[2]
            );

            System.out.printf(
                "%s: %s %s -> %s (%s)%n",
                check[0],
                check[2],
                check[1],
                result.allowed() ? "ALLOW" : "DENY",
                result.reason()
            );

            iam.authorize(
                check[0],
                check[1],
                check[2]
            );
        }

        System.out.println("\nLEAST PRIVILEGE REPORT");
        LeastPrivilegeReport report = iam.report("U001");

        System.out.println("User: " + report.username());
        System.out.println("Groups: " + report.groups());
        System.out.println("Roles: " + report.roles());
        System.out.println("Permissions: " + report.permissions());

        System.out.println("\nTEMPORARY ACCESS APPROVAL");

        AccessRequest request = iam.requestTemporaryAccess(
            "U001",
            "U003",
            "analytics",
            "read",
            30
        );

        AccessRequest approved = iam.approveTemporaryAccess(
            request.id(),
            "U003",
            30
        );

        System.out.println(
            "Request status: " + approved.status()
        );

        System.out.println(
            "Expires: " + approved.expiresAt()
        );

        System.out.println("\nACCOUNT DEACTIVATION");
        iam.updateStatus("U002", AccountStatus.DISABLED);

        System.out.println(
            "Bob report access: " +
            iam.authorize("U002", "reports", "read")
        );

        try {
            iam.requireAccess(
                "U001",
                "users",
                "delete"
            );
        } catch (AuthorizationException exception) {
            System.out.println(
                "Expected denial: " + exception.getMessage()
            );
        }

        try {
            iam.addMember("UNKNOWN", "G001");
        } catch (NotFoundException exception) {
            System.out.println(
                "Expected lookup failure: " +
                exception.getMessage()
            );
        }

        System.out.println("\nAUDIT");
        System.out.println(
            "Total events: " + iam.auditReport().size()
        );

        System.out.println(
            "Denied events: " + iam.countDeniedEvents()
        );

        System.out.println(
            "IAM execution completed."
        );
    }
}
