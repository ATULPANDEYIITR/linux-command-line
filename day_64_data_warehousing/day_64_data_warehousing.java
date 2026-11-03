import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

/*
 * Data Warehousing: enterprise ETL and governed analytical reporting.
 *
 * Java 17 features:
 *   - Records for immutable domain data.
 *   - Interfaces for source-system abstraction.
 *   - CompletableFuture for parallel extraction.
 *   - Explicit ETL job states.
 *   - SCD Type 2 customer dimensions.
 *   - Atomic warehouse batch loading.
 *   - Role-based access to pipeline and analytical operations.
 *
 * Compile and run:
 *   javac DataWarehouseDemo.java
 *   java DataWarehouseDemo
 */

public class DataWarehouseDemo {

    enum Role {
        ETL_SERVICE,
        DATA_ENGINEER,
        ANALYST
    }

    enum JobState {
        CREATED,
        EXTRACTING,
        VALIDATING,
        LOADING,
        SUCCEEDED,
        FAILED
    }

    enum SaleStatus {
        COMPLETED,
        CANCELLED,
        PENDING
    }

    record Principal(String username, Set<Role> roles) {
        Principal {
            if (username == null || username.isBlank()) {
                throw new IllegalArgumentException("Username is required");
            }
            roles = Set.copyOf(roles);
        }
    }

    record CustomerVersion(
        String customerId,
        String customerName,
        String region,
        LocalDate validFrom,
        LocalDate validTo
    ) {
        CustomerVersion {
            if (customerId == null || customerId.isBlank()) {
                throw new IllegalArgumentException("Customer ID is required");
            }
            if (customerName == null || customerName.isBlank()) {
                throw new IllegalArgumentException("Customer name is required");
            }
            if (region == null || region.isBlank()) {
                throw new IllegalArgumentException("Region is required");
            }
            if (validFrom == null || validTo == null ||
                !validFrom.isBefore(validTo)) {
                throw new IllegalArgumentException(
                    "Invalid customer validity interval"
                );
            }
        }

        boolean covers(LocalDate date) {
            return !date.isBefore(validFrom) && date.isBefore(validTo);
        }

        String businessKey() {
            return customerId + "|" + validFrom;
        }
    }

    record Product(
        String productId,
        String name,
        String category
    ) {
        Product {
            if (productId == null || productId.isBlank() ||
                name == null || name.isBlank() ||
                category == null || category.isBlank()) {
                throw new IllegalArgumentException("Invalid product");
            }
        }
    }

    record Sale(
        String saleId,
        long sourceVersion,
        String customerId,
        String productId,
        LocalDate saleDate,
        long quantity,
        long unitPriceCents,
        SaleStatus status
    ) {
        Sale {
            if (saleId == null || saleId.isBlank()) {
                throw new IllegalArgumentException("Sale ID is required");
            }
            if (sourceVersion < 1) {
                throw new IllegalArgumentException(
                    "Source version must be positive"
                );
            }
            if (customerId == null || productId == null ||
                saleDate == null || status == null) {
                throw new IllegalArgumentException(
                    "Sale fields cannot be null"
                );
            }
        }
    }

    record Fact(
        String saleId,
        long sourceVersion,
        String customerId,
        String customerRegion,
        String productId,
        String productName,
        LocalDate saleDate,
        long quantity,
        long unitPriceCents,
        long grossCents
    ) {}

    record Snapshot(
        List<CustomerVersion> customers,
        List<Product> products,
        List<Sale> sales
    ) {
        Snapshot {
            customers = List.copyOf(customers);
            products = List.copyOf(products);
            sales = List.copyOf(sales);
        }
    }

    record LoadMetrics(
        int extracted,
        int loadedOrUpdated,
        int unchanged,
        int rejected,
        int skipped,
        double rejectRatio
    ) {}

    record LoadAudit(
        String runId,
        Instant completedAt,
        LoadMetrics metrics
    ) {}

    record RevenueRow(
        String region,
        String product,
        long units,
        long revenueCents,
        long saleCount
    ) {}

    static class AccessDeniedException extends RuntimeException {
        AccessDeniedException(String message) {
            super(message);
        }
    }

    static class DataQualityException extends RuntimeException {
        DataQualityException(String message) {
            super(message);
        }
    }

    static class JobStateException extends RuntimeException {
        JobStateException(String message) {
            super(message);
        }
    }

    interface OperationalSource {
        List<CustomerVersion> extractCustomers();

        List<Product> extractProducts();

        List<Sale> extractSales();
    }

    static class InMemoryOperationalSource implements OperationalSource {
        private final List<CustomerVersion> customers = List.of(
            new CustomerVersion(
                "C001", "Asha Mehta", "North",
                LocalDate.parse("2025-01-01"),
                LocalDate.parse("2026-01-01")
            ),
            new CustomerVersion(
                "C001", "Asha Mehta", "East",
                LocalDate.parse("2026-01-01"),
                LocalDate.parse("9999-12-31")
            ),
            new CustomerVersion(
                "C002", "Rohan Singh", "South",
                LocalDate.parse("2025-01-01"),
                LocalDate.parse("9999-12-31")
            ),
            new CustomerVersion(
                "C003", "Mira Das", "West",
                LocalDate.parse("2025-01-01"),
                LocalDate.parse("9999-12-31")
            )
        );

        private final List<Product> products = List.of(
            new Product("P100", "Laptop", "Electronics"),
            new Product("P200", "Monitor", "Electronics"),
            new Product("P300", "Office Chair", "Furniture")
        );

        private final List<Sale> sales = List.of(
            new Sale(
                "S1001", 1, "C001", "P100",
                LocalDate.parse("2025-11-01"),
                2, 75000, SaleStatus.COMPLETED
            ),
            // Later source version corrects the earlier sale.
            new Sale(
                "S1001", 2, "C001", "P100",
                LocalDate.parse("2025-11-01"),
                3, 75000, SaleStatus.COMPLETED
            ),
            new Sale(
                "S1002", 1, "C002", "P200",
                LocalDate.parse("2026-02-14"),
                1, 22000, SaleStatus.COMPLETED
            ),
            new Sale(
                "S1003", 1, "C003", "P300",
                LocalDate.parse("2026-02-15"),
                3, 12000, SaleStatus.COMPLETED
            ),
            new Sale(
                "S1004", 1, "C001", "P200",
                LocalDate.parse("2026-02-16"),
                -1, 22000, SaleStatus.COMPLETED
            ),
            new Sale(
                "S1005", 1, "C404", "P100",
                LocalDate.parse("2026-02-17"),
                1, 75000, SaleStatus.COMPLETED
            ),
            new Sale(
                "S1006", 1, "C002", "P100",
                LocalDate.parse("2026-02-18"),
                1, 75000, SaleStatus.CANCELLED
            )
        );

        @Override
        public List<CustomerVersion> extractCustomers() {
            return customers;
        }

        @Override
        public List<Product> extractProducts() {
            return products;
        }

        @Override
        public List<Sale> extractSales() {
            return sales;
        }
    }

    static final class AccessPolicy {
        void requireRole(Principal principal, Role required) {
            if (principal == null || !principal.roles().contains(required)) {
                throw new AccessDeniedException(
                    "User is not authorized for role " + required
                );
            }
        }

        void requireAnyRole(Principal principal, Set<Role> allowed) {
            if (principal == null ||
                principal.roles().stream().noneMatch(allowed::contains)) {
                throw new AccessDeniedException(
                    "No permitted role was found"
                );
            }
        }
    }

    static final class JobTracker {
        private JobState state = JobState.CREATED;

        synchronized JobState state() {
            return state;
        }

        synchronized void transition(
            JobState expected,
            JobState next
        ) {
            if (state != expected) {
                throw new JobStateException(
                    "Expected " + expected + " but job is " + state
                );
            }

            boolean allowed = switch (state) {
                case CREATED -> next == JobState.EXTRACTING;
                case EXTRACTING -> next == JobState.VALIDATING;
                case VALIDATING -> next == JobState.LOADING;
                case LOADING -> next == JobState.SUCCEEDED;
                case SUCCEEDED, FAILED -> false;
            };

            if (!allowed) {
                throw new JobStateException(
                    "Illegal state transition: " + state + " -> " + next
                );
            }

            state = next;
        }

        synchronized void fail() {
            if (state != JobState.SUCCEEDED) {
                state = JobState.FAILED;
            }
        }
    }

    static final class QualityPolicy {
        private final double maximumRejectRatio;

        QualityPolicy(double maximumRejectRatio) {
            if (maximumRejectRatio < 0 || maximumRejectRatio > 1) {
                throw new IllegalArgumentException(
                    "Reject ratio must be between zero and one"
                );
            }
            this.maximumRejectRatio = maximumRejectRatio;
        }

        boolean permits(LoadMetrics metrics) {
            return metrics.extracted() > 0 &&
                   metrics.loadedOrUpdated() > 0 &&
                   metrics.rejectRatio() <= maximumRejectRatio;
        }

        double maximumRejectRatio() {
            return maximumRejectRatio;
        }
    }

    static final class Warehouse {
        private Map<String, Product> products = new HashMap<>();
        private List<CustomerVersion> customerVersions = new ArrayList<>();
        private Map<String, Fact> facts = new HashMap<>();
        private Map<String, String> quarantine = new HashMap<>();
        private List<LoadAudit> audit = new ArrayList<>();

        private static void validateCustomerTimeline(
            List<CustomerVersion> customers
        ) {
            Map<String, List<CustomerVersion>> byCustomer =
                customers.stream().collect(
                    Collectors.groupingBy(CustomerVersion::customerId)
                );

            for (Map.Entry<String, List<CustomerVersion>> entry :
                 byCustomer.entrySet()) {
                List<CustomerVersion> versions = entry.getValue().stream()
                    .sorted(Comparator.comparing(
                        CustomerVersion::validFrom
                    ))
                    .toList();

                for (int i = 1; i < versions.size(); i++) {
                    CustomerVersion previous = versions.get(i - 1);
                    CustomerVersion current = versions.get(i);

                    if (current.validFrom().isBefore(previous.validTo())) {
                        throw new DataQualityException(
                            "Overlapping SCD2 intervals for customer " +
                            entry.getKey()
                        );
                    }
                }
            }
        }

        private static CustomerVersion findCustomerVersion(
            List<CustomerVersion> versions,
            String customerId,
            LocalDate saleDate
        ) {
            return versions.stream()
                .filter(c -> c.customerId().equals(customerId))
                .filter(c -> c.covers(saleDate))
                .findFirst()
                .orElse(null);
        }

        private static long calculateGross(Sale sale) {
            if (sale.quantity() <= 0) {
                throw new DataQualityException(
                    "Quantity must be positive"
                );
            }

            if (sale.unitPriceCents() < 0) {
                throw new DataQualityException(
                    "Unit price cannot be negative"
                );
            }

            try {
                return Math.multiplyExact(
                    sale.quantity(),
                    sale.unitPriceCents()
                );
            } catch (ArithmeticException ex) {
                throw new DataQualityException(
                    "Gross amount exceeds long integer range"
                );
            }
        }

        synchronized LoadMetrics load(
            Snapshot snapshot,
            QualityPolicy policy,
            String runId
        ) {
            /*
             * The copies form a transaction workspace. Shared warehouse
             * collections are replaced only after the quality gate passes.
             */
            Map<String, Product> stagedProducts =
                new HashMap<>(products);

            List<CustomerVersion> stagedCustomers =
                new ArrayList<>(customerVersions);

            Map<String, Fact> stagedFacts =
                new HashMap<>(facts);

            Map<String, String> stagedQuarantine =
                new HashMap<>(quarantine);

            List<LoadAudit> stagedAudit = new ArrayList<>(audit);

            for (Product product : snapshot.products()) {
                stagedProducts.put(product.productId(), product);
            }

            Set<String> existingCustomerVersions =
                stagedCustomers.stream()
                    .map(CustomerVersion::businessKey)
                    .collect(Collectors.toSet());

            for (CustomerVersion customer : snapshot.customers()) {
                if (existingCustomerVersions.add(customer.businessKey())) {
                    stagedCustomers.add(customer);
                }
            }

            validateCustomerTimeline(stagedCustomers);

            int loaded = 0;
            int unchanged = 0;
            int rejected = 0;
            int skipped = 0;

            for (Sale sale : snapshot.sales()) {
                if (sale.status() != SaleStatus.COMPLETED) {
                    skipped++;
                    continue;
                }

                try {
                    Product product = stagedProducts.get(sale.productId());

                    if (product == null) {
                        throw new DataQualityException(
                            "Unknown product: " + sale.productId()
                        );
                    }

                    CustomerVersion customer = findCustomerVersion(
                        stagedCustomers,
                        sale.customerId(),
                        sale.saleDate()
                    );

                    if (customer == null) {
                        throw new DataQualityException(
                            "No valid customer dimension version for " +
                            sale.customerId() + " on " + sale.saleDate()
                        );
                    }

                    long gross = calculateGross(sale);

                    Fact previous = stagedFacts.get(sale.saleId());

                    if (previous != null &&
                        previous.sourceVersion() >= sale.sourceVersion()) {
                        unchanged++;
                        continue;
                    }

                    Fact fact = new Fact(
                        sale.saleId(),
                        sale.sourceVersion(),
                        sale.customerId(),
                        customer.region(),
                        product.productId(),
                        product.name(),
                        sale.saleDate(),
                        sale.quantity(),
                        sale.unitPriceCents(),
                        gross
                    );

                    stagedFacts.put(sale.saleId(), fact);
                    stagedQuarantine.remove(sale.saleId());
                    loaded++;
                } catch (DataQualityException ex) {
                    stagedQuarantine.put(sale.saleId(), ex.getMessage());
                    rejected++;
                }
            }

            int extracted = snapshot.sales().size();
            double rejectRatio = extracted == 0
                ? 0.0
                : (double) rejected / extracted;

            LoadMetrics metrics = new LoadMetrics(
                extracted,
                loaded,
                unchanged,
                rejected,
                skipped,
                rejectRatio
            );

            if (!policy.permits(metrics)) {
                throw new DataQualityException(
                    "Warehouse quality gate failed: reject ratio " +
                    String.format("%.3f", rejectRatio) +
                    " exceeds allowed ratio " +
                    String.format("%.3f", policy.maximumRejectRatio())
                );
            }

            stagedAudit.add(new LoadAudit(
                runId,
                Instant.now(),
                metrics
            ));

            products = stagedProducts;
            customerVersions = stagedCustomers;
            facts = stagedFacts;
            quarantine = stagedQuarantine;
            audit = stagedAudit;

            return metrics;
        }

        synchronized List<RevenueRow> revenueByRegionAndProduct() {
            Map<String, RevenueRow> grouped = new HashMap<>();

            for (Fact fact : facts.values()) {
                String key = fact.customerRegion() + "|" + fact.productName();

                RevenueRow previous = grouped.getOrDefault(
                    key,
                    new RevenueRow(
                        fact.customerRegion(),
                        fact.productName(),
                        0,
                        0,
                        0
                    )
                );

                long units = Math.addExact(
                    previous.units(),
                    fact.quantity()
                );

                long revenue = Math.addExact(
                    previous.revenueCents(),
                    fact.grossCents()
                );

                grouped.put(
                    key,
                    new RevenueRow(
                        previous.region(),
                        previous.product(),
                        units,
                        revenue,
                        previous.saleCount() + 1
                    )
                );
            }

            return grouped.values().stream()
                .sorted(
                    Comparator.comparing(RevenueRow::region)
                        .thenComparing(RevenueRow::product)
                )
                .toList();
        }

        synchronized List<Fact> facts() {
            return List.copyOf(facts.values());
        }

        synchronized Map<String, String> quarantine() {
            return Map.copyOf(quarantine);
        }

        synchronized List<LoadAudit> audit() {
            return List.copyOf(audit);
        }
    }

    static final class ETLService {
        private final OperationalSource source;
        private final Warehouse warehouse;
        private final AccessPolicy accessPolicy;
        private final QualityPolicy qualityPolicy;

        ETLService(
            OperationalSource source,
            Warehouse warehouse,
            AccessPolicy accessPolicy,
            QualityPolicy qualityPolicy
        ) {
            this.source = source;
            this.warehouse = warehouse;
            this.accessPolicy = accessPolicy;
            this.qualityPolicy = qualityPolicy;
        }

        LoadMetrics execute(
            Principal principal,
            String runId
        ) {
            accessPolicy.requireRole(principal, Role.ETL_SERVICE);

            if (runId == null || runId.isBlank()) {
                throw new IllegalArgumentException("Run ID is required");
            }

            JobTracker job = new JobTracker();
            ExecutorService executor = Executors.newFixedThreadPool(3);

            try {
                job.transition(
                    JobState.CREATED,
                    JobState.EXTRACTING
                );

                // Customer, product and sales extracts are independent
                // source operations and can be fetched concurrently.
                CompletableFuture<List<CustomerVersion>> customerFuture =
                    CompletableFuture.supplyAsync(
                        source::extractCustomers,
                        executor
                    );

                CompletableFuture<List<Product>> productFuture =
                    CompletableFuture.supplyAsync(
                        source::extractProducts,
                        executor
                    );

                CompletableFuture<List<Sale>> salesFuture =
                    CompletableFuture.supplyAsync(
                        source::extractSales,
                        executor
                    );

                Snapshot snapshot = new Snapshot(
                    customerFuture.join(),
                    productFuture.join(),
                    salesFuture.join()
                );

                job.transition(
                    JobState.EXTRACTING,
                    JobState.VALIDATING
                );

                if (snapshot.sales().isEmpty()) {
                    throw new DataQualityException(
                        "Source extraction returned no sales"
                    );
                }

                validateCustomerTimeline(snapshot.customers());

                job.transition(
                    JobState.VALIDATING,
                    JobState.LOADING
                );

                LoadMetrics metrics = warehouse.load(
                    snapshot,
                    qualityPolicy,
                    runId
                );

                job.transition(
                    JobState.LOADING,
                    JobState.SUCCEEDED
                );

                System.out.println("ETL job state: " + job.state());
                return metrics;
            } catch (CompletionException ex) {
                job.fail();
                throw new IllegalStateException(
                    "Parallel source extraction failed",
                    ex.getCause()
                );
            } catch (RuntimeException ex) {
                job.fail();
                System.err.println("ETL job state: " + job.state());
                throw ex;
            } finally {
                executor.shutdown();
            }
        }

        private static void validateCustomerTimeline(
            List<CustomerVersion> customers
        ) {
            Map<String, List<CustomerVersion>> grouped =
                customers.stream().collect(
                    Collectors.groupingBy(CustomerVersion::customerId)
                );

            for (Map.Entry<String, List<CustomerVersion>> entry :
                 grouped.entrySet()) {
                List<CustomerVersion> versions = entry.getValue().stream()
                    .sorted(Comparator.comparing(
                        CustomerVersion::validFrom
                    ))
                    .toList();

                for (int i = 1; i < versions.size(); i++) {
                    if (versions.get(i).validFrom().isBefore(
                        versions.get(i - 1).validTo()
                    )) {
                        throw new DataQualityException(
                            "Overlapping customer history for " +
                            entry.getKey()
                        );
                    }
                }
            }
        }
    }

    static final class ReportService {
        private final AccessPolicy accessPolicy;
        private final Warehouse warehouse;

        ReportService(
            AccessPolicy accessPolicy,
            Warehouse warehouse
        ) {
            this.accessPolicy = accessPolicy;
            this.warehouse = warehouse;
        }

        List<RevenueRow> revenueReport(Principal principal) {
            accessPolicy.requireAnyRole(
                principal,
                Set.of(Role.ANALYST, Role.DATA_ENGINEER)
            );

            return warehouse.revenueByRegionAndProduct();
        }
    }

    public static void main(String[] args) {
        AccessPolicy accessPolicy = new AccessPolicy();
        QualityPolicy qualityPolicy = new QualityPolicy(0.30);
        Warehouse warehouse = new Warehouse();

        OperationalSource source = new InMemoryOperationalSource();

        Principal etlPrincipal = new Principal(
            "warehouse-service",
            Set.of(Role.ETL_SERVICE)
        );

        Principal analystPrincipal = new Principal(
            "business-analyst",
            Set.of(Role.ANALYST)
        );

        ETLService etlService = new ETLService(
            source,
            warehouse,
            accessPolicy,
            qualityPolicy
        );

        ReportService reportService = new ReportService(
            accessPolicy,
            warehouse
        );

        try {
            LoadMetrics metrics = etlService.execute(
                etlPrincipal,
                "RUN-2026-11-03-001"
            );

            System.out.println("\nETL metrics");
            System.out.println("Extracted: " + metrics.extracted());
            System.out.println("Loaded/updated: " + metrics.loadedOrUpdated());
            System.out.println("Unchanged: " + metrics.unchanged());
            System.out.println("Rejected: " + metrics.rejected());
            System.out.println("Skipped: " + metrics.skipped());
            System.out.printf(
                "Reject ratio: %.2f%%%n",
                metrics.rejectRatio() * 100
            );

            System.out.println("\nAnalytical report");
            for (RevenueRow row :
                 reportService.revenueReport(analystPrincipal)) {
                System.out.printf(
                    "%-10s %-15s units=%d sales=%d revenue=%.2f%n",
                    row.region(),
                    row.product(),
                    row.units(),
                    row.saleCount(),
                    row.revenueCents() / 100.0
                );
            }

            System.out.println("\nFact records: " + warehouse.facts().size());

            System.out.println("\nQuarantined records");
            warehouse.quarantine().forEach(
                (saleId, reason) ->
                    System.out.println(saleId + ": " + reason)
            );

            System.out.println("\nLoad audit");
            for (LoadAudit audit : warehouse.audit()) {
                System.out.println(
                    audit.runId() + " at " + audit.completedAt()
                );
            }

            // A user without a reporting role must not read analytical data.
            Principal unauthorized = new Principal(
                "read-only-guest",
                Set.of()
            );

            try {
                reportService.revenueReport(unauthorized);
                throw new IllegalStateException(
                    "Access-control test failed"
                );
            } catch (AccessDeniedException expected) {
                System.out.println("\nUnauthorized report access blocked.");
            }

            if (warehouse.facts().size() != 3) {
                throw new IllegalStateException(
                    "Unexpected number of warehouse facts"
                );
            }

            System.out.println("All checks passed.");
        } catch (RuntimeException ex) {
            System.err.println("Enterprise ETL failure: " + ex.getMessage());
            System.exitCode = 1;
        }
    }
}
