```python
"""
CLOUD SERVICE MODELS
====================

Topic:
Cloud Service Models - Understand IaaS, PaaS, SaaS, FaaS, and compare
responsibilities between cloud providers and customers.

This program is written as a structured learning script. It explains the
technology stack, cloud abstraction, shared responsibility, IaaS, PaaS,
SaaS, FaaS, security responsibilities, scalability, cost characteristics,
vendor lock-in, observability, workload selection, and practical comparisons.

The examples are simulations and educational demonstrations. They do not
connect to an actual cloud provider.
"""


# =============================================================================
# 1. INTRODUCTION
# =============================================================================

print("=" * 90)
print("CLOUD SERVICE MODELS")
print("=" * 90)

print("""
Cloud computing is the delivery of computing resources and capabilities
through a network, usually using infrastructure operated by a cloud service
provider.

The major cloud service models are:

    IaaS  - Infrastructure as a Service
    PaaS  - Platform as a Service
    SaaS  - Software as a Service
    FaaS  - Function as a Service

These models differ mainly in the amount of infrastructure and software that
the cloud provider manages on behalf of the customer.

The fundamental question is:

    Who manages which part of the technology stack?

A cloud service model establishes a responsibility boundary between the
provider and the customer.

As a general principle:

    More provider management
        ->
    More abstraction
        ->
    Less customer infrastructure management
        ->
    Less low-level infrastructure control

Conversely:

    More customer management
        ->
    More control
        ->
    More customization
        ->
    More operational responsibility
""")


# =============================================================================
# 2. THE TRADITIONAL ON-PREMISES MODEL
# =============================================================================

print("\n" + "=" * 90)
print("TRADITIONAL ON-PREMISES COMPUTING")
print("=" * 90)

on_premises_layers = [
    "Physical facility",
    "Power and cooling",
    "Physical networking",
    "Physical storage",
    "Physical servers",
    "Virtualization",
    "Operating system",
    "Middleware",
    "Runtime",
    "Application",
    "Data"
]

for layer in on_premises_layers:
    print(f"- {layer}")

print("""
In a traditional on-premises environment, the organization may be
responsible for almost every layer.

For example, a company operating its own data center may need to:

    - Purchase servers
    - Purchase storage systems
    - Install networking equipment
    - Provide power
    - Provide cooling
    - Maintain physical security
    - Replace failed hardware
    - Install operating systems
    - Configure software
    - Deploy applications
    - Protect data

Cloud computing changes this arrangement by moving some of these
responsibilities to a provider.

The amount transferred depends on the service model.
""")


# =============================================================================
# 3. TECHNOLOGY STACK
# =============================================================================

print("\n" + "=" * 90)
print("THE CLOUD TECHNOLOGY STACK")
print("=" * 90)

technology_stack = [
    ("Physical Facility", "Buildings, physical security, power, cooling"),
    ("Networking", "Connectivity, routing, switching, network infrastructure"),
    ("Storage", "Physical and logical storage infrastructure"),
    ("Servers", "Physical computing hardware"),
    ("Virtualization", "Virtual machines and resource abstraction"),
    ("Operating System", "Linux, Windows, and other operating systems"),
    ("Middleware", "Supporting software between applications and OS"),
    ("Runtime", "Python, Java, Node.js, .NET, and similar environments"),
    ("Application", "Business and application logic"),
    ("Data", "Information created and processed by applications")
]

for layer, explanation in technology_stack:
    print(f"{layer:<22} : {explanation}")


# =============================================================================
# 4. SHARED RESPONSIBILITY MODEL
# =============================================================================

print("\n" + "=" * 90)
print("SHARED RESPONSIBILITY MODEL")
print("=" * 90)

print("""
The shared responsibility model divides responsibility between:

    Cloud Provider
        and
    Cloud Customer

The provider is responsible for the infrastructure and managed components
under its control.

The customer is responsible for the components and configurations under
customer control.

The exact boundary changes according to the service.

A critical concept is:

    Provider responsibility does not equal customer responsibility.

A provider may operate secure physical infrastructure while the customer
can still expose data through an incorrect configuration.

For example, customers may remain responsible for:

    - Identity
    - Access permissions
    - Data
    - Application code
    - Application configuration
    - Credentials
    - Secrets
    - Data sharing
""")


# =============================================================================
# 5. GENERIC CLOUD SERVICE MODEL
# =============================================================================

class CloudServiceModel:
    """
    Represents a conceptual cloud service model.

    This class is used to demonstrate the division of responsibility between
    a provider and customer.
    """

    def __init__(self, name, provider_managed, customer_managed):
        self.name = name
        self.provider_managed = provider_managed
        self.customer_managed = customer_managed

    def display(self):
        print("\n" + "-" * 90)
        print(self.name)
        print("-" * 90)

        print("\nProvider manages:")
        for item in self.provider_managed:
            print(f"  [P] {item}")

        print("\nCustomer manages:")
        for item in self.customer_managed:
            print(f"  [C] {item}")


# =============================================================================
# 6. IAAS
# =============================================================================

print("\n" + "=" * 90)
print("INFRASTRUCTURE AS A SERVICE - IAAS")
print("=" * 90)

print("""
IaaS stands for Infrastructure as a Service.

IaaS provides fundamental computing infrastructure as a service.

Typical resources include:

    - Virtual machines
    - Virtual networks
    - Storage
    - IP addresses
    - Load balancers
    - Virtual disks
    - Firewalls
    - Computing capacity

The cloud provider manages the physical infrastructure and virtualization
layer.

The customer usually manages the operating system and everything above it.

This gives IaaS customers substantial control over their computing
environment.
""")


iaas = CloudServiceModel(
    "Infrastructure as a Service (IaaS)",

    provider_managed=[
        "Physical facility",
        "Power and cooling",
        "Physical servers",
        "Physical networking",
        "Physical storage",
        "Virtualization"
    ],

    customer_managed=[
        "Operating system",
        "Operating system configuration",
        "Operating system patches",
        "Middleware",
        "Runtime",
        "Application",
        "Application configuration",
        "Data",
        "Application-level security"
    ]
)

iaas.display()


# =============================================================================
# 7. IAAS VIRTUAL MACHINE SIMULATION
# =============================================================================

class VirtualMachine:
    """
    Simulates a virtual machine in an IaaS environment.
    """

    def __init__(self, name, operating_system, cpu, memory_gb):
        self.name = name
        self.operating_system = operating_system
        self.cpu = cpu
        self.memory_gb = memory_gb
        self.status = "STOPPED"

    def start(self):
        self.status = "RUNNING"

    def stop(self):
        self.status = "STOPPED"

    def information(self):
        print("\nVirtual Machine")
        print("-" * 40)
        print(f"Name       : {self.name}")
        print(f"OS         : {self.operating_system}")
        print(f"CPU        : {self.cpu} cores")
        print(f"Memory     : {self.memory_gb} GB")
        print(f"Status     : {self.status}")


vm = VirtualMachine(
    name="application-server",
    operating_system="Linux",
    cpu=4,
    memory_gb=16
)

vm.information()
vm.start()
vm.information()


print("""
In this example, the virtual machine represents the infrastructure supplied
by an IaaS platform.

The customer may still have to:

    1. Configure Linux.
    2. Install security updates.
    3. Install application dependencies.
    4. Configure network rules.
    5. Deploy the application.
    6. Monitor the operating system.
    7. Protect credentials.
    8. Configure backups.
    9. Maintain application security.

The physical server itself is not managed by the customer.
The virtual machine environment is exposed to the customer as an
infrastructure resource.
""")


# =============================================================================
# 8. IAAS ADVANTAGES
# =============================================================================

print("\n" + "=" * 90)
print("IAAS ADVANTAGES")
print("=" * 90)

iaas_advantages = [
    "High infrastructure-level control",
    "Operating system flexibility",
    "Custom software installation",
    "Custom runtime environments",
    "Infrastructure customization",
    "Elastic resource provisioning",
    "Reduced physical hardware ownership",
    "Useful for traditional applications",
    "Useful for specialized workloads"
]

for item in iaas_advantages:
    print(f"- {item}")


# =============================================================================
# 9. IAAS LIMITATIONS
# =============================================================================

print("\n" + "=" * 90)
print("IAAS LIMITATIONS")
print("=" * 90)

iaas_limitations = [
    "Operating system administration remains necessary",
    "Security patching remains necessary",
    "Application deployment remains customer responsibility",
    "More infrastructure configuration is required",
    "More monitoring responsibility exists",
    "More technical administration is required",
    "Misconfiguration can create security problems"
]

for item in iaas_limitations:
    print(f"- {item}")


# =============================================================================
# 10. PAAS
# =============================================================================

print("\n" + "=" * 90)
print("PLATFORM AS A SERVICE - PAAS")
print("=" * 90)

print("""
PaaS stands for Platform as a Service.

PaaS provides a managed environment for application development and
deployment.

The cloud provider manages more layers than in IaaS.

The customer generally focuses on:

    - Application code
    - Application configuration
    - Data

The provider manages much of:

    - Infrastructure
    - Operating system
    - Runtime
    - Middleware
    - Platform maintenance

PaaS is designed to reduce infrastructure administration for application
development teams.
""")


paas = CloudServiceModel(
    "Platform as a Service (PaaS)",

    provider_managed=[
        "Physical facility",
        "Physical networking",
        "Physical storage",
        "Physical servers",
        "Virtualization",
        "Operating system",
        "Middleware",
        "Runtime",
        "Platform infrastructure"
    ],

    customer_managed=[
        "Application code",
        "Application configuration",
        "Application security",
        "Application data",
        "User permissions"
    ]
)

paas.display()


# =============================================================================
# 11. PAAS DEPLOYMENT SIMULATION
# =============================================================================

class PaaSApplication:
    """
    Simulates an application deployed to a managed platform.
    """

    def __init__(self, name, language, version):
        self.name = name
        self.language = language
        self.version = version
        self.status = "NOT DEPLOYED"

    def deploy(self):
        self.status = "RUNNING"

    def display(self):
        print("\nPaaS Application")
        print("-" * 40)
        print(f"Application : {self.name}")
        print(f"Language    : {self.language}")
        print(f"Version     : {self.version}")
        print(f"Status      : {self.status}")


application = PaaSApplication(
    name="student-portal",
    language="Python",
    version="3.x"
)

application.display()
application.deploy()
application.display()


print("""
The developer focuses on the application.

The platform provides much of the environment required to execute the
application.

A simplified deployment process becomes:

    Write Code
        ->
    Configure Application
        ->
    Deploy
        ->
    Platform Executes Application

The customer does not necessarily need to manage the underlying virtual
machines or operating systems.
""")


# =============================================================================
# 12. PAAS ADVANTAGES
# =============================================================================

print("\n" + "=" * 90)
print("PAAS ADVANTAGES")
print("=" * 90)

paas_advantages = [
    "Reduced server administration",
    "Managed operating system",
    "Managed runtime",
    "Faster deployment",
    "Developer-focused workflow",
    "Platform-level scaling capabilities",
    "Reduced infrastructure maintenance",
    "Standardized application environments"
]

for item in paas_advantages:
    print(f"- {item}")


# =============================================================================
# 13. PAAS LIMITATIONS
# =============================================================================

print("\n" + "=" * 90)
print("PAAS LIMITATIONS")
print("=" * 90)

paas_limitations = [
    "Reduced operating system control",
    "Limited platform customization",
    "Supported runtime restrictions",
    "Platform-specific deployment requirements",
    "Possible vendor lock-in",
    "Possible dependency restrictions"
]

for item in paas_limitations:
    print(f"- {item}")


# =============================================================================
# 14. SAAS
# =============================================================================

print("\n" + "=" * 90)
print("SOFTWARE AS A SERVICE - SAAS")
print("=" * 90)

print("""
SaaS stands for Software as a Service.

SaaS provides a complete software application to customers.

The customer generally does not manage:

    - Physical servers
    - Virtual machines
    - Operating systems
    - Runtime environments
    - Application servers
    - Core application software

The provider operates the application.

Customers usually interact with the application through:

    - Web browsers
    - Mobile applications
    - Desktop applications
    - APIs

SaaS is therefore a highly managed service model.
""")


saas = CloudServiceModel(
    "Software as a Service (SaaS)",

    provider_managed=[
        "Physical facility",
        "Networking",
        "Storage infrastructure",
        "Physical servers",
        "Virtualization",
        "Operating system",
        "Middleware",
        "Runtime",
        "Application infrastructure",
        "Core application"
    ],

    customer_managed=[
        "Customer data",
        "Users",
        "Access permissions",
        "Application configuration",
        "Data governance",
        "Appropriate use"
    ]
)

saas.display()


# =============================================================================
# 15. SAAS USER SIMULATION
# =============================================================================

class SaaSApplication:
    """
    Simulates customer usage of a SaaS application.
    """

    def __init__(self, name):
        self.name = name
        self.users = {}
        self.data = []

    def add_user(self, username, role):
        self.users[username] = role

    def add_data(self, item):
        self.data.append(item)

    def show_users(self):
        print(f"\nUsers of {self.name}")

        for username, role in self.users.items():
            print(f"- {username}: {role}")

    def show_data(self):
        print(f"\nData stored in {self.name}")

        for item in self.data:
            print(f"- {item}")


saas_app = SaaSApplication("Business Collaboration Platform")

saas_app.add_user("administrator", "Admin")
saas_app.add_user("employee01", "Employee")
saas_app.add_user("employee02", "Employee")

saas_app.add_data("Business Document")
saas_app.add_data("Project Information")

saas_app.show_users()
saas_app.show_data()


print("""
The SaaS provider operates the application.

The customer still controls important aspects such as:

    - User accounts
    - Roles
    - Permissions
    - Data
    - Sharing configuration
    - Application settings

This distinction is critical.

A provider can secure the SaaS infrastructure while a customer can still
create a security problem through incorrect access configuration.
""")


# =============================================================================
# 16. SAAS ADVANTAGES
# =============================================================================

print("\n" + "=" * 90)
print("SAAS ADVANTAGES")
print("=" * 90)

saas_advantages = [
    "Complete application is available",
    "Minimal infrastructure administration",
    "Provider manages application updates",
    "Fast adoption",
    "No need to manage application servers",
    "Reduced operational infrastructure burden"
]

for item in saas_advantages:
    print(f"- {item}")


# =============================================================================
# 17. SAAS LIMITATIONS
# =============================================================================

print("\n" + "=" * 90)
print("SAAS LIMITATIONS")
print("=" * 90)

saas_limitations = [
    "Limited application-level customization",
    "Limited infrastructure control",
    "Dependency on provider availability",
    "Potential vendor lock-in",
    "Provider-defined feature boundaries",
    "Limited control over application internals"
]

for item in saas_limitations:
    print(f"- {item}")


# =============================================================================
# 18. FAAS
# =============================================================================

print("\n" + "=" * 90)
print("FUNCTION AS A SERVICE - FAAS")
print("=" * 90)

print("""
FaaS stands for Function as a Service.

FaaS allows developers to deploy individual units of executable application
logic called functions.

Functions are commonly executed in response to events.

Examples of events include:

    - HTTP requests
    - File uploads
    - Database changes
    - Queue messages
    - Scheduled events
    - Notifications
    - Events from other cloud services

FaaS is strongly associated with serverless computing.

Serverless does not mean that servers do not exist.

Servers still execute the code.

The term means that the customer does not directly manage the servers
required for function execution.
""")


faas = CloudServiceModel(
    "Function as a Service (FaaS)",

    provider_managed=[
        "Physical facility",
        "Physical servers",
        "Networking infrastructure",
        "Storage infrastructure",
        "Virtualization",
        "Operating system",
        "Function execution infrastructure",
        "Infrastructure provisioning",
        "Infrastructure scaling"
    ],

    customer_managed=[
        "Function code",
        "Business logic",
        "Function configuration",
        "Event configuration",
        "Permissions",
        "Secrets",
        "Application dependencies",
        "Data"
    ]
)

faas.display()


# =============================================================================
# 19. FAAS FUNCTION SIMULATION
# =============================================================================

def process_uploaded_file(event):
    """
    Simulates an event-triggered cloud function.
    """

    file_name = event.get("file_name")
    file_size = event.get("file_size")

    print("\nFunction Invocation")
    print("-" * 40)
    print(f"File name : {file_name}")
    print(f"File size : {file_size} MB")

    return {
        "status": "processed",
        "file": file_name
    }


upload_event = {
    "file_name": "report.csv",
    "file_size": 20
}

function_result = process_uploaded_file(upload_event)

print("\nFunction result:")
print(function_result)


# =============================================================================
# 20. EVENT-DRIVEN ARCHITECTURE
# =============================================================================

print("\n" + "=" * 90)
print("EVENT-DRIVEN ARCHITECTURE")
print("=" * 90)

print("""
A common FaaS architecture follows this pattern:

    Event
      |
      v
    Trigger
      |
      v
    Function
      |
      v
    Processing
      |
      v
    Result

Example:

    File Upload
        |
        v
    Storage Event
        |
        v
    Function
        |
        v
    Image Processing
        |
        v
    Processed Image

The function does not need to continuously run simply to wait for the
event.

The cloud platform manages the execution infrastructure.
""")


# =============================================================================
# 21. STATELESSNESS
# =============================================================================

print("\n" + "=" * 90)
print("STATELESSNESS IN FAAS")
print("=" * 90)

print("""
FaaS applications are commonly designed to be stateless.

A function should not depend on local memory from a previous invocation.

An unsafe assumption would be:

    Invocation 1
        ->
    Save important state in local memory
        ->
    Invocation 2
        ->
    Assume the state is still present

The execution environment may have been terminated.

Persistent state should generally be stored in external systems such as:

    - Databases
    - Object storage
    - Distributed caches
    - Managed storage systems
""")


# =============================================================================
# 22. COLD STARTS
# =============================================================================

print("\n" + "=" * 90)
print("COLD STARTS")
print("=" * 90)

print("""
A cold start occurs when a new function execution environment needs to be
initialized.

The process may involve:

    1. Allocating an execution environment.
    2. Starting the runtime.
    3. Loading dependencies.
    4. Initializing application code.
    5. Executing the function.

This initialization can add latency.

Cold-start behavior can depend on:

    - Runtime technology
    - Dependency size
    - Application package size
    - Initialization logic
    - Network configuration
    - Platform implementation

A warm environment may already exist and may require less initialization.
""")


# =============================================================================
# 23. FAAS CONCURRENCY
# =============================================================================

print("\n" + "=" * 90)
print("FAAS CONCURRENCY")
print("=" * 90)


class FunctionExecution:
    """
    Represents one function invocation.
    """

    def __init__(self, execution_id, event):
        self.execution_id = execution_id
        self.event = event

    def execute(self):
        print(
            f"Execution {self.execution_id} "
            f"processing event '{self.event}'"
        )


events = [
    "file_uploaded",
    "payment_received",
    "user_registered",
    "database_updated"
]

executions = []

for number, event in enumerate(events, start=1):
    executions.append(FunctionExecution(number, event))

for execution in executions:
    execution.execute()


print("""
Multiple events can result in multiple function executions.

Conceptually:

    Event 1 -> Function Instance A
    Event 2 -> Function Instance B
    Event 3 -> Function Instance C
    Event 4 -> Function Instance D

This allows event-driven workloads to scale.

Scaling still has boundaries.

Possible constraints include:

    - Concurrency limits
    - Service quotas
    - Account limits
    - Database connection limits
    - API rate limits
    - Downstream service capacity
""")


# =============================================================================
# 24. RESPONSIBILITY MATRIX
# =============================================================================

print("\n" + "=" * 90)
print("RESPONSIBILITY MATRIX")
print("=" * 90)

responsibility_matrix = {
    "Physical facility": ["Provider", "Provider", "Provider", "Provider"],
    "Physical servers": ["Provider", "Provider", "Provider", "Provider"],
    "Networking": ["Provider", "Provider", "Provider", "Provider"],
    "Storage infrastructure": ["Provider", "Provider", "Provider", "Provider"],
    "Virtualization": ["Provider", "Provider", "Provider", "Provider"],
    "Operating system": ["Customer", "Provider", "Provider", "Provider"],
    "Middleware": ["Customer", "Provider", "Provider", "Provider"],
    "Runtime": ["Customer", "Provider", "Provider", "Provider"],
    "Application": ["Customer", "Customer", "Provider", "Customer"],
    "Data": ["Customer", "Customer", "Customer", "Customer"]
}

print(
    f"{'Layer':<28}"
    f"{'IaaS':<15}"
    f"{'PaaS':<15}"
    f"{'SaaS':<15}"
    f"{'FaaS':<15}"
)

print("-" * 88)

for layer, values in responsibility_matrix.items():

    print(
        f"{layer:<28}"
        f"{values[0]:<15}"
        f"{values[1]:<15}"
        f"{values[2]:<15}"
        f"{values[3]:<15}"
    )


# =============================================================================
# 25. SERVICE MODEL COMPARISON
# =============================================================================

print("\n" + "=" * 90)
print("SERVICE MODEL COMPARISON")
print("=" * 90)

comparison = {
    "IaaS": {
        "control": "High",
        "abstraction": "Lower",
        "server_management": "Customer",
        "os_management": "Customer",
        "application_management": "Customer",
        "primary_focus": "Infrastructure"
    },

    "PaaS": {
        "control": "Medium",
        "abstraction": "Higher",
        "server_management": "Provider",
        "os_management": "Provider",
        "application_management": "Customer",
        "primary_focus": "Application development"
    },

    "SaaS": {
        "control": "Low",
        "abstraction": "Very high",
        "server_management": "Provider",
        "os_management": "Provider",
        "application_management": "Provider",
        "primary_focus": "Software consumption"
    },

    "FaaS": {
        "control": "Low infrastructure control",
        "abstraction": "Very high",
        "server_management": "Provider",
        "os_management": "Provider",
        "application_management": "Customer",
        "primary_focus": "Function execution"
    }
}

for model, details in comparison.items():

    print(f"\n{model}")

    for key, value in details.items():
        print(f"  {key:<22}: {value}")


# =============================================================================
# 26. CONTROL VS ABSTRACTION
# =============================================================================

print("\n" + "=" * 90)
print("CONTROL VS ABSTRACTION")
print("=" * 90)

print("""
IaaS generally provides the greatest infrastructure control.

PaaS moves operating system and runtime management to the provider.

FaaS abstracts server infrastructure and focuses on event-driven execution.

SaaS provides an entire application.

A simplified conceptual relationship is:

    More infrastructure control
                |
               IaaS
                |
               PaaS
                |
               FaaS
                |
               SaaS
                |
    More provider abstraction

This is a conceptual representation.

FaaS and SaaS are not simply different versions of the same service.

FaaS is primarily a development and execution model.

SaaS is primarily a software consumption model.
""")


# =============================================================================
# 27. SECURITY RESPONSIBILITIES
# =============================================================================

print("\n" + "=" * 90)
print("SECURITY RESPONSIBILITIES")
print("=" * 90)

security = {
    "IaaS": [
        "Operating system hardening",
        "Operating system patching",
        "Virtual machine security",
        "Application security",
        "Network configuration",
        "Identity and access",
        "Data protection"
    ],

    "PaaS": [
        "Application code security",
        "Application configuration",
        "Authentication",
        "Authorization",
        "Secrets",
        "Data protection"
    ],

    "SaaS": [
        "User management",
        "Access permissions",
        "Data sharing",
        "Application configuration",
        "Data governance"
    ],

    "FaaS": [
        "Function code security",
        "Function permissions",
        "Event validation",
        "Secrets",
        "Dependencies",
        "Data access"
    ]
}

for model, responsibilities in security.items():

    print(f"\n{model}")

    for responsibility in responsibilities:
        print(f"  - {responsibility}")


# =============================================================================
# 28. IDENTITY AND ACCESS MANAGEMENT
# =============================================================================

print("\n" + "=" * 90)
print("IDENTITY AND ACCESS MANAGEMENT")
print("=" * 90)

print("""
Identity and access management is relevant to every cloud service model.

The customer may need to determine:

    - Who can access the service?
    - What can each user access?
    - Which identities are administrators?
    - Which services can communicate with each other?
    - Which permissions are necessary?
    - Which permissions are excessive?

The principle of least privilege is important.

Least privilege means giving an identity only the permissions required to
perform its intended task.

For example:

    A function that only reads objects from a storage location should not
    automatically receive administrative access to the entire cloud account.
""")


# =============================================================================
# 29. CONFIGURATION SECURITY
# =============================================================================

print("\n" + "=" * 90)
print("CONFIGURATION AS A SECURITY BOUNDARY")
print("=" * 90)

configuration_risks = [
    "Publicly exposed resources",
    "Excessive permissions",
    "Weak authentication",
    "Exposed credentials",
    "Poor secret management",
    "Incorrect network rules",
    "Unrestricted API access",
    "Incorrect data-sharing settings"
]

for risk in configuration_risks:
    print(f"- {risk}")

print("""
A cloud provider can operate secure infrastructure while a customer
configuration creates an exposure.

Therefore:

    Provider security
          +
    Customer configuration
          +
    Application security
          +
    Data protection

together influence the security posture of the cloud workload.
""")


# =============================================================================
# 30. SCALABILITY
# =============================================================================

print("\n" + "=" * 90)
print("SCALABILITY")
print("=" * 90)

print("""
Scalability is the ability of a system to handle changes in workload.

The responsibility for scalability differs by service model.

IaaS:
    Customers may configure virtual machine scaling, load balancing, and
    capacity management.

PaaS:
    The platform can provide managed scaling capabilities.

SaaS:
    The provider manages application infrastructure scaling.

FaaS:
    Function execution can scale according to events and workload, subject
    to quotas and downstream capacity.
""")


# =============================================================================
# 31. COST CHARACTERISTICS
# =============================================================================

print("\n" + "=" * 90)
print("COST CHARACTERISTICS")
print("=" * 90)

cost_characteristics = {
    "IaaS": [
        "Virtual machine capacity",
        "Storage",
        "Network usage",
        "Provisioned infrastructure"
    ],

    "PaaS": [
        "Application capacity",
        "Platform resources",
        "Storage",
        "Network usage"
    ],

    "SaaS": [
        "Users",
        "Subscriptions",
        "Features",
        "Storage",
        "Usage"
    ],

    "FaaS": [
        "Function invocations",
        "Execution duration",
        "Memory allocation",
        "Associated services"
    ]
}

for model, factors in cost_characteristics.items():

    print(f"\n{model}")

    for factor in factors:
        print(f"  - {factor}")


print("""
Cloud pricing is provider-specific.

The service model gives a general understanding of what is being consumed,
but the actual billing mechanism depends on the specific service.

A significant IaaS characteristic is that provisioned resources can generate
cost even when they are not actively processing useful workload.

FaaS can be attractive for workloads that execute intermittently because
the customer does not necessarily need to maintain a continuously running
application server for every function.
""")


# =============================================================================
# 32. VENDOR LOCK-IN
# =============================================================================

print("\n" + "=" * 90)
print("VENDOR LOCK-IN")
print("=" * 90)

print("""
Vendor lock-in occurs when moving an application or workload from one
provider to another becomes difficult.

Potential causes include:

    - Proprietary APIs
    - Provider-specific databases
    - Proprietary event systems
    - Platform-specific deployment mechanisms
    - Provider-specific identity systems
    - Specialized managed services

IaaS can sometimes provide greater portability because customers have more
control over the operating environment.

PaaS and FaaS can introduce stronger dependencies on provider-specific
platform capabilities.

SaaS can introduce application-level dependency because the customer is
consuming the provider's complete software product.
""")


# =============================================================================
# 33. OBSERVABILITY
# =============================================================================

print("\n" + "=" * 90)
print("OBSERVABILITY")
print("=" * 90)

observability = {
    "IaaS": [
        "CPU utilization",
        "Memory usage",
        "Disk usage",
        "Operating system logs",
        "Network traffic"
    ],

    "PaaS": [
        "Application response time",
        "Request count",
        "Application errors",
        "Runtime metrics",
        "Application logs"
    ],

    "SaaS": [
        "User activity",
        "Audit logs",
        "Application usage",
        "Access events",
        "Service availability"
    ],

    "FaaS": [
        "Invocation count",
        "Execution duration",
        "Error rate",
        "Timeouts",
        "Concurrency",
        "Cold starts"
    ]
}

for model, metrics in observability.items():

    print(f"\n{model}")

    for metric in metrics:
        print(f"  - {metric}")


# =============================================================================
# 34. FAILURE DOMAINS
# =============================================================================

print("\n" + "=" * 90)
print("FAILURE DOMAINS")
print("=" * 90)

failure_causes = [
    "Incorrect application code",
    "Invalid configuration",
    "Permission errors",
    "Database failures",
    "Network failures",
    "External API failures",
    "Data problems",
    "Dependency failures",
    "Resource limits"
]

for cause in failure_causes:
    print(f"- {cause}")

print("""
A managed service reduces certain infrastructure responsibilities but does
not eliminate application failure.

For example:

    Application
         |
         v
    Managed API
         |
         v
    Database
         |
         v
    External Service

A failure in the database or external service can still affect the
application even when the underlying cloud infrastructure is healthy.

Cloud architecture therefore requires understanding dependencies and
failure boundaries.
""")


# =============================================================================
# 35. WORKLOAD REPRESENTATION
# =============================================================================

class Workload:
    """
    Represents workload characteristics used to reason about service model
    selection.
    """

    def __init__(
        self,
        name,
        requires_os_control=False,
        requires_custom_infrastructure=False,
        application_development=False,
        event_driven=False,
        complete_application_required=False
    ):
        self.name = name
        self.requires_os_control = requires_os_control
        self.requires_custom_infrastructure = requires_custom_infrastructure
        self.application_development = application_development
        self.event_driven = event_driven
        self.complete_application_required = complete_application_required

    def possible_model(self):

        if self.complete_application_required:
            return "SaaS"

        if self.event_driven:
            return "FaaS"

        if (
            self.requires_os_control
            or self.requires_custom_infrastructure
        ):
            return "IaaS"

        if self.application_development:
            return "PaaS"

        return "Depends on workload requirements"


workloads = [

    Workload(
        name="Legacy application",
        requires_os_control=True,
        requires_custom_infrastructure=True,
        application_development=True
    ),

    Workload(
        name="Custom web application",
        application_development=True
    ),

    Workload(
        name="Image processing after file upload",
        application_development=True,
        event_driven=True
    ),

    Workload(
        name="Business productivity software",
        complete_application_required=True
    )
]

print("\n" + "=" * 90)
print("WORKLOAD MODEL SELECTION")
print("=" * 90)

for workload in workloads:

    print(f"\nWorkload: {workload.name}")
    print(f"Possible model: {workload.possible_model()}")


# =============================================================================
# 36. MULTI-MODEL ARCHITECTURE
# =============================================================================

print("\n" + "=" * 90)
print("MULTI-MODEL CLOUD ARCHITECTURE")
print("=" * 90)

print("""
An organization does not have to use only one service model.

A single organization can use:

    SaaS
        for business productivity

    PaaS
        for custom web applications

    FaaS
        for event processing

    IaaS
        for specialized or legacy systems

A conceptual architecture may look like:

                     Organization
                          |
        +-----------------+-----------------+
        |                 |                 |
       SaaS              PaaS              IaaS
        |                 |                 |
 Business Software   Web Application   Legacy System
                          |
                         FaaS
                          |
                   Event Processing

Different workloads have different requirements, so multiple service models
can coexist within one organization.
""")


# =============================================================================
# 37. IAAS VS PAAS
# =============================================================================

print("\n" + "=" * 90)
print("IAAS VS PAAS")
print("=" * 90)

print("""
IaaS:

    Provider
        - Physical infrastructure
        - Virtualization

    Customer
        - Operating system
        - Runtime
        - Middleware
        - Application
        - Data

PaaS:

    Provider
        - Physical infrastructure
        - Virtualization
        - Operating system
        - Middleware
        - Runtime

    Customer
        - Application
        - Data

The main difference is the operating environment.

IaaS exposes infrastructure.

PaaS exposes a managed platform for application development.
""")


# =============================================================================
# 38. PAAS VS FAAS
# =============================================================================

print("\n" + "=" * 90)
print("PAAS VS FAAS")
print("=" * 90)

print("""
PaaS commonly supports an application as a managed service.

FaaS commonly supports independent functions triggered by events.

PaaS examples:

    - Web applications
    - APIs
    - Application backends
    - Long-running services

FaaS examples:

    - File processing
    - Event handlers
    - Scheduled functions
    - Queue processing
    - Data transformation

The distinction is largely related to application execution and deployment
patterns.
""")


# =============================================================================
# 39. FAAS VS SAAS
# =============================================================================

print("\n" + "=" * 90)
print("FAAS VS SAAS")
print("=" * 90)

print("""
FaaS is primarily a development and execution model.

SaaS is primarily a software consumption model.

With FaaS:

    Developer
        ->
    Function Code
        ->
    Cloud Execution Environment

With SaaS:

    User
        ->
    Complete Application
        ->
    Cloud Provider

FaaS is used to execute customer-written application logic.

SaaS is used to consume provider-operated software.
""")


# =============================================================================
# 40. PORTABILITY
# =============================================================================

print("\n" + "=" * 90)
print("PORTABILITY")
print("=" * 90)

print("""
Portability refers to how easily a workload can be moved between different
environments or providers.

Portability can be affected by:

    - Operating system dependencies
    - Runtime dependencies
    - Database technologies
    - Provider-specific APIs
    - Deployment mechanisms
    - Identity systems
    - Storage systems
    - Event systems

IaaS may provide more control over the operating environment.

PaaS may restrict the environment but simplify development.

FaaS may simplify event-driven execution but introduce dependencies on
provider-specific function platforms.

SaaS can create strong application-level dependency because the customer is
consuming a complete provider-operated application.
""")


# =============================================================================
# 41. COMMON MISUNDERSTANDINGS
# =============================================================================

print("\n" + "=" * 90)
print("COMMON MISUNDERSTANDINGS")
print("=" * 90)

misunderstandings = {
    "Cloud means there are no servers":
        "Servers still exist. Their management is abstracted from the customer.",

    "SaaS means the customer has no security responsibility":
        "Customers still manage users, permissions, configuration, and data.",

    "PaaS means the provider manages application code":
        "The customer normally remains responsible for application code.",

    "Serverless means servers do not exist":
        "Servers still execute the functions; their management is abstracted.",

    "IaaS means the provider secures everything":
        "The customer remains responsible for customer-managed layers.",

    "More abstraction is always better":
        "More abstraction reduces operational work but can reduce control."
}

for misunderstanding, correction in misunderstandings.items():

    print(f"\nMisunderstanding:")
    print(f"  {misunderstanding}")

    print("Correction:")
    print(f"  {correction}")


# =============================================================================
# 42. COMPLETE RESPONSIBILITY VIEW
# =============================================================================

print("\n" + "=" * 90)
print("COMPLETE RESPONSIBILITY VIEW")
print("=" * 90)

print("""
IAAS
----

Provider:
    Physical facility
    Hardware
    Networking
    Storage
    Virtualization

Customer:
    Operating system
    Middleware
    Runtime
    Application
    Data


PAAS
----

Provider:
    Physical facility
    Hardware
    Networking
    Storage
    Virtualization
    Operating system
    Middleware
    Runtime

Customer:
    Application
    Data


SAAS
----

Provider:
    Physical facility
    Hardware
    Networking
    Storage
    Virtualization
    Operating system
    Middleware
    Runtime
    Application

Customer:
    Users
    Permissions
    Configuration
    Data


FAAS
----

Provider:
    Physical facility
    Hardware
    Networking
    Storage infrastructure
    Virtualization
    Operating system
    Function execution environment
    Infrastructure scaling

Customer:
    Function code
    Function configuration
    Events
    Permissions
    Data
""")


# =============================================================================
# 43. SERVICE MODEL DECISION QUESTIONS
# =============================================================================

print("\n" + "=" * 90)
print("SERVICE MODEL DECISION QUESTIONS")
print("=" * 90)

decision_questions = [
    (
        "Do you require operating system control?",
        "IaaS generally provides greater control."
    ),

    (
        "Do you primarily want to develop and deploy applications?",
        "PaaS can reduce infrastructure administration."
    ),

    (
        "Do you need a complete ready-to-use application?",
        "SaaS can provide the complete software."
    ),

    (
        "Is your workload event-driven?",
        "FaaS can provide event-triggered execution."
    ),

    (
        "Do you need extensive infrastructure customization?",
        "IaaS generally provides the greatest infrastructure control."
    ),

    (
        "Do you want to minimize server administration?",
        "PaaS, SaaS, or FaaS may reduce infrastructure management."
    )
]

for question, interpretation in decision_questions:

    print(f"\nQuestion: {question}")
    print(f"Interpretation: {interpretation}")


# =============================================================================
# 44. FINAL TECHNICAL MODEL
# =============================================================================

print("\n" + "=" * 90)
print("CLOUD SERVICE MODEL RELATIONSHIP")
print("=" * 90)

print("""
                    CUSTOMER CONTROL
                          ^
                          |
                         IaaS
                          |
                         PaaS
                          |
                         FaaS
                          |
                         SaaS
                          |
                          v
                   PROVIDER ABSTRACTION


IaaS
    Infrastructure is abstracted, but the customer controls much of the
    operating environment.

PaaS
    Infrastructure and platform management are abstracted, allowing the
    customer to concentrate on application development.

FaaS
    Server infrastructure and execution environments are abstracted, while
    the customer deploys event-driven functions.

SaaS
    The complete application is provided and operated by the provider, while
    the customer primarily manages users, configuration, access, and data.

The service model therefore defines a responsibility boundary.

The more infrastructure a provider manages, the less infrastructure the
customer must directly operate.

The customer nevertheless retains responsibility for the resources,
configurations, identities, applications, and data that remain under
customer control.
""")
```

````markdown
# Cloud Service Models

## IaaS, PaaS, SaaS, FaaS and the Shared Responsibility Model

Cloud service models describe different ways of consuming computing resources and software through cloud providers. The central idea behind these models is not simply where an application runs. The important issue is **who manages each layer of the technology stack**.

The four major models covered are:

- Infrastructure as a Service (IaaS)
- Platform as a Service (PaaS)
- Software as a Service (SaaS)
- Function as a Service (FaaS)

Each model establishes a different boundary between the cloud provider and the customer.

The more infrastructure the provider manages, the greater the abstraction provided to the customer. The customer generally performs less infrastructure administration but also has less low-level control.

---

## Traditional On-Premises Computing

In a traditional on-premises environment, an organization can be responsible for almost every component required to operate its computing environment.

A simplified stack is:

```text
Physical Facility
Power and Cooling
Networking
Storage
Servers
Virtualization
Operating System
Middleware
Runtime
Application
Data
````

The organization may need to purchase and maintain physical servers, storage equipment, networking equipment, power systems, cooling systems, operating systems, application environments, and software.

Hardware failures are also the organization's responsibility.

Cloud computing changes this arrangement by moving some of these responsibilities to a cloud provider.

The amount of responsibility transferred depends on the selected service model.

---

# Technology Stack

Understanding the cloud service models requires understanding the layers involved in a computing environment.

## Physical Facility

The physical facility includes the data center building, physical security, power infrastructure, cooling systems, and related facilities.

## Networking

Networking provides communication between users, applications, servers, databases, and external systems.

It includes:

* Connectivity
* Routing
* Network segmentation
* Network interfaces
* Firewalls
* Load balancing
* Network infrastructure

## Storage

Storage provides persistent capacity for:

* Files
* Databases
* Backups
* Logs
* Application assets
* Business data

## Servers

Servers provide computing resources such as CPU and memory.

## Virtualization

Virtualization abstracts physical computing resources into logical environments such as virtual machines.

## Operating System

The operating system manages computing resources and provides an environment for applications.

Examples include Linux and Windows.

## Middleware

Middleware provides supporting functionality between applications and lower-level system components.

It can support:

* Communication
* Messaging
* Integration
* Authentication
* Application services

## Runtime

A runtime provides the environment required to execute application code.

Examples include:

* Python
* Java
* Node.js
* .NET

## Application

The application contains the business logic and functionality used by customers or users.

## Data

Data consists of information created, processed, stored, and consumed by applications.

---

# Shared Responsibility Model

Cloud computing uses a shared responsibility model.

Responsibility is divided between:

```text
Cloud Provider
       +
Cloud Customer
```

The provider manages the infrastructure and services that are under the provider's control.

The customer manages the resources, configurations, applications, identities, and data that remain under customer control.

The boundary changes depending on the service.

A critical point is that **provider-managed infrastructure does not mean that the customer has no security responsibility**.

For example, the provider may secure:

* Physical facilities
* Physical servers
* Core networking
* Virtualization infrastructure

The customer may still be responsible for:

* User accounts
* Access permissions
* Application configuration
* Application code
* Credentials
* Secrets
* Data
* Data sharing

The shared responsibility model therefore changes the location of responsibility rather than eliminating responsibility.

---

# Infrastructure as a Service

## Definition

Infrastructure as a Service, or IaaS, provides fundamental computing infrastructure through the cloud.

Typical IaaS resources include:

* Virtual machines
* Virtual networks
* Virtual disks
* Storage
* IP addresses
* Load balancers
* Firewalls
* Computing capacity

IaaS provides significant infrastructure-level control to customers.

The cloud provider operates the physical infrastructure.

The customer usually manages the operating system and the software environment above the virtualization layer.

---

# IaaS Responsibility Model

A simplified IaaS responsibility boundary is:

| Layer               | Responsibility |
| ------------------- | -------------- |
| Physical facility   | Provider       |
| Power and cooling   | Provider       |
| Physical networking | Provider       |
| Physical storage    | Provider       |
| Physical servers    | Provider       |
| Virtualization      | Provider       |
| Operating system    | Customer       |
| Middleware          | Customer       |
| Runtime             | Customer       |
| Application         | Customer       |
| Data                | Customer       |

The exact responsibility boundary can differ according to the specific cloud service.

---

# What the Customer Manages in IaaS

In IaaS, customers may be responsible for:

* Selecting the operating system
* Configuring the operating system
* Installing operating system updates
* Installing software
* Installing runtimes
* Installing application dependencies
* Configuring network rules
* Deploying applications
* Monitoring virtual machines
* Managing credentials
* Protecting applications
* Protecting data
* Configuring backups

For example, a customer may provision a Linux virtual machine and then install Python, application dependencies, and an application.

The provider supplies the virtualized infrastructure, but the customer manages the software environment running inside the virtual machine.

---

# IaaS Example

A conceptual IaaS deployment looks like:

```text
Customer
   |
   +-- Linux
   +-- Python
   +-- Application Dependencies
   +-- Application
   +-- Data

Provider
   |
   +-- Virtual Machine Infrastructure
   +-- Virtualization
   +-- Physical Servers
   +-- Physical Storage
   +-- Physical Networking
   +-- Data Center
```

The customer receives substantial control over the virtual computing environment.

---

# IaaS Advantages

IaaS provides:

* High infrastructure-level control
* Operating system flexibility
* Custom software installation
* Custom runtime environments
* Infrastructure customization
* Elastic resource provisioning
* Reduced physical hardware ownership
* Support for traditional applications
* Support for specialized workloads

IaaS is particularly useful when an application requires direct control over the operating system or a customized server environment.

---

# IaaS Limitations

IaaS does not eliminate infrastructure administration.

The customer may still need to perform:

* Operating system patching
* Security hardening
* Runtime configuration
* Application deployment
* Application maintenance
* Backup configuration
* Monitoring
* Capacity planning
* Access control

The customer therefore gains control at the cost of additional operational responsibility.

---

# Platform as a Service

## Definition

Platform as a Service, or PaaS, provides a managed environment for developing and deploying applications.

Compared with IaaS, PaaS moves more responsibility to the cloud provider.

The provider generally manages:

* Infrastructure
* Operating system
* Middleware
* Runtime
* Platform infrastructure

The customer generally manages:

* Application code
* Application configuration
* Application security
* Application data

The primary objective of PaaS is to reduce the amount of infrastructure administration required from application development teams.

---

# PaaS Responsibility Model

A simplified PaaS responsibility boundary is:

| Layer                     | Responsibility |
| ------------------------- | -------------- |
| Physical facility         | Provider       |
| Physical servers          | Provider       |
| Networking                | Provider       |
| Storage                   | Provider       |
| Virtualization            | Provider       |
| Operating system          | Provider       |
| Middleware                | Provider       |
| Runtime                   | Provider       |
| Application               | Customer       |
| Application configuration | Customer       |
| Data                      | Customer       |

The customer does not normally manage the underlying operating system.

---

# PaaS Development Model

Without PaaS, a developer may need to perform:

```text
Provision Server
      ↓
Install Operating System
      ↓
Patch Operating System
      ↓
Install Runtime
      ↓
Install Dependencies
      ↓
Configure Server
      ↓
Deploy Application
```

With PaaS, the workflow can be simplified:

```text
Write Application
      ↓
Configure Application
      ↓
Deploy
      ↓
Platform Executes Application
```

The platform provides much of the environment required for execution.

---

# PaaS Advantages

PaaS can provide:

* Reduced server administration
* Managed operating systems
* Managed runtime environments
* Faster deployment
* Developer-focused workflows
* Platform-level scaling capabilities
* Reduced infrastructure maintenance
* Standardized application environments

Developers can spend more time working on application functionality instead of managing servers.

---

# PaaS Limitations

PaaS can introduce restrictions because the provider manages the platform.

Possible limitations include:

* Limited operating system access
* Limited platform customization
* Runtime version restrictions
* Dependency restrictions
* Platform-specific deployment requirements
* Provider-specific configuration
* Vendor lock-in

A customer requiring a highly customized operating system or runtime may prefer IaaS.

---

# Software as a Service

## Definition

Software as a Service, or SaaS, provides a complete software application to customers.

The customer consumes the application rather than managing the infrastructure and software stack required to operate it.

SaaS applications can be accessed through:

* Web browsers
* Mobile applications
* Desktop applications
* APIs

The provider generally manages the application infrastructure and the application itself.

---

# SaaS Responsibility Model

A simplified SaaS responsibility boundary is:

| Layer                      | Responsibility |
| -------------------------- | -------------- |
| Physical facility          | Provider       |
| Physical servers           | Provider       |
| Networking                 | Provider       |
| Storage infrastructure     | Provider       |
| Virtualization             | Provider       |
| Operating system           | Provider       |
| Middleware                 | Provider       |
| Runtime                    | Provider       |
| Application                | Provider       |
| Application infrastructure | Provider       |
| Users                      | Customer       |
| Permissions                | Customer       |
| Configuration              | Customer       |
| Data                       | Customer       |

The customer does not generally manage the underlying operating system or application servers.

---

# SaaS Customer Responsibilities

Even though the provider operates the application, customers still manage important areas.

These can include:

* User accounts
* User roles
* Access permissions
* Data
* Data sharing
* Application configuration
* Data governance
* Appropriate use

For example, a SaaS application can have strong infrastructure security while a customer administrator accidentally gives a user excessive permissions.

The infrastructure can be secure while the customer configuration is insecure.

---

# SaaS Advantages

SaaS provides:

* Complete applications
* Minimal infrastructure administration
* Provider-managed application updates
* Fast adoption
* No requirement to manage application servers
* Reduced operational infrastructure burden

The customer can use the software without building and maintaining the underlying application platform.

---

# SaaS Limitations

SaaS can involve:

* Limited application customization
* Limited infrastructure control
* Provider dependency
* Application-level vendor lock-in
* Provider-defined functionality
* Limited access to application internals

The customer generally has much less control over how the application itself is implemented.

---

# Function as a Service

## Definition

Function as a Service, or FaaS, provides an execution environment for individual functions.

A function is a unit of executable application logic.

FaaS is commonly associated with serverless computing.

Serverless does not mean that servers do not exist.

Servers still execute the code.

The distinction is that the customer does not directly manage the servers used to execute the function.

---

# Event-Driven Execution

FaaS is strongly associated with event-driven architecture.

A function can be triggered by:

* HTTP requests
* File uploads
* Database changes
* Queue messages
* Scheduled events
* Notifications
* Events generated by other cloud services

A simplified architecture is:

```text
Event
  ↓
Trigger
  ↓
Function
  ↓
Processing
  ↓
Result
```

For example:

```text
File Upload
    ↓
Storage Event
    ↓
Function Invocation
    ↓
File Processing
    ↓
Processed File
```

The function does not need to continuously execute while waiting for an event.

---

# FaaS Responsibility Model

A simplified FaaS responsibility boundary is:

| Layer                       | Responsibility |
| --------------------------- | -------------- |
| Physical facility           | Provider       |
| Physical servers            | Provider       |
| Networking                  | Provider       |
| Storage infrastructure      | Provider       |
| Virtualization              | Provider       |
| Operating system            | Provider       |
| Execution infrastructure    | Provider       |
| Infrastructure provisioning | Provider       |
| Infrastructure scaling      | Provider       |
| Function code               | Customer       |
| Function configuration      | Customer       |
| Event configuration         | Customer       |
| Permissions                 | Customer       |
| Data                        | Customer       |

The customer focuses on the function and its associated configuration.

---

# FaaS Advantages

FaaS can provide:

* Reduced server administration
* Event-driven execution
* Automatic infrastructure provisioning
* Automatic scaling mechanisms
* Independent function execution
* Rapid deployment of small application components
* Usage-oriented execution

FaaS is particularly useful when application operations can be expressed as independent functions.

---

# Statelessness in FaaS

FaaS applications are commonly designed to be stateless.

A function should not assume that local memory from one invocation will exist during a later invocation.

An unsafe pattern is:

```text
Invocation 1
    ↓
Store important state in local memory
    ↓
Invocation 2
    ↓
Assume previous state still exists
```

The execution environment may have been terminated.

Persistent state should generally be stored externally.

Examples include:

* Databases
* Object storage
* Distributed caches
* Managed storage systems

This design allows function executions to be created, reused, or terminated independently.

---

# FaaS Cold Starts

A cold start occurs when the cloud platform needs to initialize a new execution environment.

Initialization can involve:

1. Allocating an execution environment
2. Starting the runtime
3. Loading dependencies
4. Initializing application code
5. Executing the function

Cold starts can introduce additional latency.

Their behavior can depend on:

* Runtime technology
* Dependency size
* Package size
* Initialization logic
* Network configuration
* Platform implementation

A warm execution environment may already be available and may require less initialization work.

---

# FaaS Concurrency

Multiple events can result in multiple function executions.

For example:

```text
Event 1 → Function Instance A
Event 2 → Function Instance B
Event 3 → Function Instance C
Event 4 → Function Instance D
```

This allows event-driven applications to process multiple requests concurrently.

Scaling still has limits.

Possible constraints include:

* Concurrency limits
* Service quotas
* Account limits
* Database connection limits
* API rate limits
* Downstream service capacity

A function can scale quickly while a dependency such as a database may not be capable of handling the same growth rate.

---

# Responsibility Matrix

The core responsibility relationship can be summarized as:

| Layer                  | IaaS     | PaaS     | SaaS     | FaaS     |
| ---------------------- | -------- | -------- | -------- | -------- |
| Physical facility      | Provider | Provider | Provider | Provider |
| Physical servers       | Provider | Provider | Provider | Provider |
| Networking             | Provider | Provider | Provider | Provider |
| Storage infrastructure | Provider | Provider | Provider | Provider |
| Virtualization         | Provider | Provider | Provider | Provider |
| Operating system       | Customer | Provider | Provider | Provider |
| Middleware             | Customer | Provider | Provider | Provider |
| Runtime                | Customer | Provider | Provider | Provider |
| Application            | Customer | Customer | Provider | Customer |
| Data                   | Customer | Customer | Customer | Customer |

This is a conceptual model. Specific services can have different responsibility boundaries.

---

# IaaS, PaaS, SaaS and FaaS Comparison

| Characteristic               | IaaS           | PaaS                    | SaaS                 | FaaS               |
| ---------------------------- | -------------- | ----------------------- | -------------------- | ------------------ |
| Infrastructure control       | High           | Medium                  | Low                  | Low                |
| Server management            | Customer       | Provider                | Provider             | Provider           |
| OS management                | Customer       | Provider                | Provider             | Provider           |
| Runtime management           | Customer       | Provider                | Provider             | Provider           |
| Application management       | Customer       | Customer                | Provider             | Customer           |
| Data responsibility          | Customer       | Customer                | Customer             | Customer           |
| Infrastructure customization | High           | Limited                 | Very limited         | Limited            |
| Server administration        | High           | Low                     | Minimal              | Minimal            |
| Main focus                   | Infrastructure | Application development | Software consumption | Function execution |
| Event-driven orientation     | Not inherent   | Not inherent            | Not inherent         | Strong             |

---

# Control Versus Abstraction

Cloud service models can be understood as different points on the control and abstraction spectrum.

A simplified representation is:

```text
More Infrastructure Control
          |
         IaaS
          |
         PaaS
          |
         FaaS
          |
         SaaS
          |
More Provider Abstraction
```

IaaS generally provides greater infrastructure control.

PaaS provides greater platform abstraction.

FaaS abstracts server infrastructure and focuses on event-driven function execution.

SaaS provides a complete application.

FaaS and SaaS should not be interpreted as identical services arranged on a simple scale. They serve different architectural purposes.

FaaS is primarily a development and execution model.

SaaS is primarily a software consumption model.

---

# IaaS Versus PaaS

The difference between IaaS and PaaS is primarily the amount of platform management transferred to the provider.

## IaaS

```text
Provider
    Physical Infrastructure
    Virtualization

Customer
    Operating System
    Middleware
    Runtime
    Application
    Data
```

## PaaS

```text
Provider
    Physical Infrastructure
    Virtualization
    Operating System
    Middleware
    Runtime

Customer
    Application
    Data
```

IaaS gives the customer greater infrastructure control.

PaaS allows the customer to concentrate more heavily on application development.

---

# PaaS Versus FaaS

PaaS and FaaS both reduce infrastructure administration, but they commonly support different execution patterns.

PaaS is suitable for:

* Web applications
* APIs
* Application backends
* Long-running services

FaaS is suitable for:

* Event handlers
* File processing
* Queue processing
* Scheduled functions
* Data transformation
* Background event processing

The primary distinction is the application execution model.

A PaaS application can remain available as a deployed service.

A FaaS function generally executes when triggered.

---

# FaaS Versus SaaS

FaaS and SaaS operate at different levels.

FaaS is mainly consumed by developers.

The developer provides the function code.

```text
Developer
    ↓
Function Code
    ↓
Cloud Execution Platform
```

SaaS is mainly consumed by users or organizations.

The provider provides the complete application.

```text
User
    ↓
Complete Application
    ↓
Cloud Provider
```

FaaS is therefore an application execution model, while SaaS is a complete software delivery model.

---

# Security Responsibilities

The service model affects security responsibilities.

## IaaS Security

Customers may need to secure:

* Operating systems
* Virtual machines
* Network configuration
* Applications
* Credentials
* Data

## PaaS Security

Customers generally focus on:

* Application code
* Application configuration
* Authentication
* Authorization
* Secrets
* Data

## SaaS Security

Customers commonly focus on:

* Users
* Permissions
* Configuration
* Data sharing
* Data governance

## FaaS Security

Customers need to consider:

* Function code
* Function permissions
* Event validation
* Secrets
* Dependencies
* Data access

---

# Identity and Access Management

Identity and access management is relevant to all cloud service models.

Customers may need to determine:

* Who can access resources
* What each user can access
* Which users are administrators
* Which services can communicate
* Which permissions are necessary
* Which permissions are excessive

The principle of least privilege is important.

Least privilege means that an identity receives only the permissions required to perform its intended task.

For example, a function that only needs to read files from a particular storage location should not automatically receive administrative access to the entire cloud environment.

---

# Configuration as a Security Boundary

A cloud provider can operate secure infrastructure while customer configuration can still create vulnerabilities.

Common configuration risks include:

* Publicly exposed resources
* Excessive permissions
* Weak authentication
* Exposed credentials
* Poor secret management
* Incorrect network rules
* Unrestricted API access
* Incorrect data-sharing configuration

Cloud security therefore involves multiple layers:

```text
Provider Infrastructure Security
            +
Customer Configuration Security
            +
Application Security
            +
Identity Security
            +
Data Protection
```

---

# Scalability

Scalability is the ability of a system to handle changes in workload.

The responsibility for scaling changes according to the service model.

## IaaS

Customers may configure:

* Multiple virtual machines
* Load balancers
* Autoscaling
* Capacity
* Network resources

## PaaS

The platform can provide managed scaling mechanisms.

The customer focuses more on application behavior and configuration.

## SaaS

The provider manages the infrastructure and application capacity.

The customer consumes the application according to the service's available limits.

## FaaS

Function execution can scale according to event volume.

Customers still need to consider:

* Concurrency
* Quotas
* Execution limits
* Database capacity
* API limits
* Downstream services

Automatic scaling does not mean that every component of the architecture can scale without limits.

---

# Cost Characteristics

The service model also affects how cloud costs are commonly structured.

## IaaS

Costs can depend on:

* Virtual machine capacity
* Storage
* Network traffic
* Provisioned resources
* Running resources

A provisioned resource may continue generating cost even when it is underutilized.

## PaaS

Costs can depend on:

* Application capacity
* Platform resources
* Storage
* Network usage
* Platform features

The customer pays for a more managed environment.

## SaaS

Costs are often related to:

* Number of users
* Subscription
* Features
* Storage
* Usage

## FaaS

Costs can depend on:

* Function invocations
* Execution duration
* Memory allocation
* Associated cloud services

Actual pricing depends on the specific provider and service.

---

# Vendor Lock-In

Vendor lock-in occurs when moving an application or workload from one provider to another becomes difficult.

Potential causes include:

* Proprietary APIs
* Provider-specific databases
* Provider-specific event systems
* Platform-specific deployment mechanisms
* Provider-specific identity services
* Specialized managed services

IaaS can sometimes provide greater portability because the customer controls more of the operating environment.

PaaS can introduce dependencies on platform-specific capabilities.

FaaS can introduce dependencies on provider-specific event and execution systems.

SaaS can create application-level dependency because the customer is consuming the provider's complete application.

Vendor lock-in is therefore an architectural and business consideration.

---

# Portability

Portability describes how easily a workload can move between environments.

Portability can be affected by:

* Operating system dependencies
* Runtime dependencies
* Database technology
* Provider APIs
* Deployment mechanisms
* Identity systems
* Storage interfaces
* Event systems

A workload based on standardized technologies may be easier to migrate than a workload tightly coupled to proprietary services.

At the same time, provider-specific services can offer significant operational and technical advantages.

Portability therefore involves a trade-off between flexibility and the benefits of managed services.

---

# Observability

Observability refers to the ability to understand the behavior of a system through logs, metrics, traces, events, and other telemetry.

The monitoring emphasis changes according to the service model.

## IaaS

Monitoring can include:

* CPU utilization
* Memory utilization
* Disk utilization
* Operating system logs
* Network traffic
* Process status

## PaaS

Monitoring can focus on:

* Application response time
* Request count
* Application errors
* Runtime metrics
* Application logs

## SaaS

Customers may monitor:

* User activity
* Audit logs
* Application usage
* Access events
* Service availability

## FaaS

Monitoring can include:

* Invocation count
* Execution duration
* Error rate
* Timeout rate
* Concurrency
* Cold starts

Greater abstraction does not eliminate observability requirements. It changes the type of information available to the customer.

---

# Failure Domains

Managed cloud services reduce some infrastructure responsibilities but do not eliminate failures.

Cloud applications can still fail because of:

* Incorrect application code
* Invalid configuration
* Permission errors
* Database failures
* Network failures
* External API failures
* Invalid data
* Dependency failures
* Resource limits

A managed application may depend on several other services.

For example:

```text
Application
     ↓
Managed API
     ↓
Database
     ↓
External Service
```

If the database or external service becomes unavailable, the application can be affected even if the underlying cloud infrastructure remains operational.

Cloud architecture therefore requires understanding dependencies and failure boundaries.

---

# Multi-Model Cloud Architecture

Organizations do not need to select only one service model.

Multiple models can coexist.

For example:

```text
Organization
     |
     +---- SaaS
     |       Business Productivity
     |
     +---- PaaS
     |       Web Application
     |
     +---- FaaS
     |       Event Processing
     |
     +---- IaaS
             Legacy Application
```

A single architecture can also combine several service types.

For example:

```text
Web Application
      ↓
PaaS
      ↓
Managed Database
      ↓
FaaS
      ↓
Object Storage
```

Different components can use different service models according to their requirements.

---

# Workload Selection

## IaaS

IaaS is generally suitable when:

* Operating system control is required
* Infrastructure customization is necessary
* Specialized software must be installed
* Existing applications require server-level control
* Infrastructure-level configuration is important

## PaaS

PaaS is generally suitable when:

* Application development is the main objective
* Infrastructure administration should be reduced
* The application can operate within platform constraints
* A managed runtime is desirable

## SaaS

SaaS is generally suitable when:

* A complete application already satisfies the requirement
* The organization does not need to build the application
* Infrastructure management should be minimized
* Users need software capabilities rather than application infrastructure

## FaaS

FaaS is generally suitable when:

* Workloads are event-driven
* Individual operations can execute independently
* Server administration should be minimized
* Workload demand changes dynamically
* Functions can operate independently

---

# Common Misunderstandings

## Cloud Means There Are No Servers

Cloud services still depend on physical servers.

The difference is that customers do not necessarily own or directly manage those servers.

---

## SaaS Means the Customer Has No Security Responsibility

SaaS reduces infrastructure responsibility.

Customers still manage areas such as:

* Users
* Permissions
* Data
* Configuration
* Data sharing

---

## PaaS Means the Provider Manages the Application

PaaS generally means that the provider manages the platform.

The customer normally remains responsible for application code and application-level security.

---

## Serverless Means There Are No Servers

Servers still execute serverless functions.

The customer simply does not directly manage the server infrastructure.

---

## IaaS Means the Provider Secures Everything

The provider secures infrastructure under provider control.

The customer remains responsible for customer-managed components such as operating systems, applications, identities, and data.

---

## More Abstraction Is Always Better

More abstraction reduces operational responsibility but can reduce infrastructure control and customization.

The appropriate service model depends on the workload.

---

# Complete Responsibility View

## IaaS

```text
Provider
├── Physical Facility
├── Physical Servers
├── Networking
├── Storage
└── Virtualization

Customer
├── Operating System
├── Middleware
├── Runtime
├── Application
└── Data
```

## PaaS

```text
Provider
├── Physical Facility
├── Physical Servers
├── Networking
├── Storage
├── Virtualization
├── Operating System
├── Middleware
└── Runtime

Customer
├── Application
└── Data
```

## SaaS

```text
Provider
├── Physical Facility
├── Physical Servers
├── Networking
├── Storage
├── Virtualization
├── Operating System
├── Middleware
├── Runtime
└── Application

Customer
├── Users
├── Permissions
├── Configuration
└── Data
```

## FaaS

```text
Provider
├── Physical Facility
├── Physical Servers
├── Networking
├── Storage Infrastructure
├── Virtualization
├── Operating System
├── Execution Infrastructure
└── Infrastructure Scaling

Customer
├── Function Code
├── Function Configuration
├── Events
├── Permissions
└── Data
```

---

# Control and Responsibility

The fundamental relationship can be expressed as:

```text
More Customer Control
        ↓
More Customer Responsibility
        ↓
IaaS
        ↓
PaaS
        ↓
FaaS / SaaS
        ↓
More Provider Abstraction
```

IaaS provides significant infrastructure control while leaving substantial software and operational responsibility with the customer.

PaaS transfers operating system, middleware, and runtime management to the provider while allowing the customer to concentrate on applications.

FaaS abstracts server infrastructure and provides event-driven execution while leaving function logic, configuration, permissions, and data under customer responsibility.

SaaS provides a complete application and transfers most infrastructure and application management to the provider while leaving users, permissions, configuration, and data responsibilities with the customer.

The defining characteristic of cloud service models is therefore the **division of responsibility across the technology stack**.

The selected service model determines the level of infrastructure control, operational workload, customization, security responsibility, deployment model, scalability behavior, cost characteristics, and provider dependency associated with a workload.

```
```

