"""
Cloud Service Models: IaaS, PaaS, SaaS, and FaaS
=================================================

This script explains the major cloud service models from basic concepts to
advanced architectural and operational considerations.

The focus is on:
    - Infrastructure as a Service (IaaS)
    - Platform as a Service (PaaS)
    - Software as a Service (SaaS)
    - Function as a Service (FaaS)
    - Responsibility distribution between cloud providers and customers
    - Security, scalability, cost, deployment, and operational implications
    - Practical scenarios for selecting an appropriate cloud service model

The examples use Python classes and simulations rather than connecting to
real cloud infrastructure. The objective is to represent how responsibility
and abstraction change across cloud service models.
"""


# =============================================================================
# 1. INTRODUCTION TO CLOUD SERVICE MODELS
# =============================================================================

print("=" * 80)
print("CLOUD SERVICE MODELS")
print("=" * 80)

print("""
Cloud computing provides computing resources over a network instead of
requiring an organization to purchase, install, and maintain all physical
infrastructure independently.

A traditional on-premises environment typically requires an organization to
manage nearly every layer of the technology stack. Cloud computing changes
this arrangement by transferring some responsibilities to a cloud provider.

The degree of responsibility transferred depends on the cloud service model.

The major service models discussed in this program are:

1. IaaS - Infrastructure as a Service
2. PaaS - Platform as a Service
3. SaaS - Software as a Service
4. FaaS - Function as a Service

A useful way to understand these models is to examine how much of the
technology stack is managed by the customer and how much is managed by the
cloud provider.
""")


# =============================================================================
# 2. THE TECHNOLOGY STACK
# =============================================================================

print("=" * 80)
print("THE CLOUD TECHNOLOGY STACK")
print("=" * 80)

technology_stack = [
    "Applications",
    "Data",
    "Runtime",
    "Middleware",
    "Operating System",
    "Virtualization",
    "Servers",
    "Storage",
    "Networking"
]

for position, layer in enumerate(technology_stack, start=1):
    print(f"{position}. {layer}")


print("""
These layers represent different parts of a computing environment.

Applications:
    Software used to perform business or user-facing functions.

Data:
    Information created, stored, processed, and consumed by applications.

Runtime:
    The execution environment required for an application, such as Python,
    Java, Node.js, or another programming environment.

Middleware:
    Software positioned between applications and the operating system that
    supports communication, integration, authentication, messaging, and
    other services.

Operating System:
    Software responsible for managing hardware resources and providing an
    environment in which applications execute.

Virtualization:
    Technology that abstracts physical hardware into virtual machines,
    containers, or other logical computing environments.

Servers:
    Physical computing hardware providing processing capacity.

Storage:
    Systems used to persist files, databases, objects, backups, and other
    information.

Networking:
    Infrastructure responsible for communication between systems, users,
    applications, and external networks.
""")


# =============================================================================
# 3. RESPONSIBILITY MODEL
# =============================================================================

print("=" * 80)
print("SHARED RESPONSIBILITY MODEL")
print("=" * 80)

print("""
Cloud computing does not eliminate customer responsibility.

Instead, responsibility is divided between:

    Cloud Provider
        The organization supplying cloud infrastructure and services.

    Customer
        The organization or individual consuming those services.

The exact boundary changes according to the service model.

As abstraction increases:

    - The provider manages more infrastructure.
    - The customer manages fewer technical layers.
    - The customer gains convenience.
    - The customer loses some low-level control.

This trade-off between control and convenience is central to cloud
architecture.
""")


# =============================================================================
# 4. BASE CLASS FOR SERVICE MODELS
# =============================================================================

class CloudServiceModel:
    """
    Represents a generic cloud service model.

    Each service model divides responsibility between the provider and
    customer across the layers of the technology stack.
    """

    def __init__(self, name, provider_managed, customer_managed):
        self.name = name
        self.provider_managed = provider_managed
        self.customer_managed = customer_managed

    def display_responsibilities(self):
        print("\n" + "=" * 80)
        print(f"{self.name}")
        print("=" * 80)

        print("\nProvider Managed:")
        for item in self.provider_managed:
            print(f"  - {item}")

        print("\nCustomer Managed:")
        for item in self.customer_managed:
            print(f"  - {item}")


# =============================================================================
# 5. INFRASTRUCTURE AS A SERVICE - IAAS
# =============================================================================

print("\n" + "=" * 80)
print("INFRASTRUCTURE AS A SERVICE - IAAS")
print("=" * 80)

print("""
Infrastructure as a Service provides fundamental computing resources through
the cloud.

Typical resources include:

    - Virtual machines
    - Virtual networks
    - Storage
    - Load balancers
    - Firewalls
    - Processing capacity

The provider manages the underlying physical infrastructure and virtualization
layer.

The customer retains responsibility for the operating system and everything
above it.

IaaS provides substantial flexibility because customers can configure virtual
machines and operating environments according to their requirements.

This flexibility also creates additional operational responsibility.
""")


iaas = CloudServiceModel(
    name="Infrastructure as a Service (IaaS)",
    provider_managed=[
        "Networking infrastructure",
        "Physical storage hardware",
        "Physical servers",
        "Data center facilities",
        "Power and cooling",
        "Virtualization infrastructure"
    ],
    customer_managed=[
        "Operating system",
        "Middleware",
        "Runtime",
        "Applications",
        "Data",
        "Application configuration",
        "Operating system updates",
        "Virtual machine configuration"
    ]
)

iaas.display_responsibilities()


# =============================================================================
# 6. IAAS EXAMPLE
# =============================================================================

class VirtualMachine:
    """
    Simulates a virtual machine created through an IaaS environment.
    """

    def __init__(self, name, operating_system, cpu_cores, memory_gb):
        self.name = name
        self.operating_system = operating_system
        self.cpu_cores = cpu_cores
        self.memory_gb = memory_gb
        self.status = "Stopped"

    def start(self):
        self.status = "Running"
        print(f"Virtual machine '{self.name}' is now running.")

    def stop(self):
        self.status = "Stopped"
        print(f"Virtual machine '{self.name}' has been stopped.")

    def display_configuration(self):
        print("\nVirtual Machine Configuration")
        print("-" * 40)
        print(f"Name: {self.name}")
        print(f"Operating System: {self.operating_system}")
        print(f"CPU Cores: {self.cpu_cores}")
        print(f"Memory: {self.memory_gb} GB")
        print(f"Status: {self.status}")


print("\nIaaS Example")

server = VirtualMachine(
    name="application-server",
    operating_system="Linux",
    cpu_cores=4,
    memory_gb=16
)

server.display_configuration()
server.start()


print("""
In an IaaS environment, the provider supplies the virtualized infrastructure.

The customer may still need to:

    - Select an operating system.
    - Configure the operating system.
    - Install security updates.
    - Configure networking.
    - Install application dependencies.
    - Deploy applications.
    - Monitor resource utilization.
    - Configure backups.
    - Protect applications and data.

IaaS is therefore appropriate when infrastructure-level control is important.
""")


# =============================================================================
# 7. ADVANTAGES OF IAAS
# =============================================================================

print("=" * 80)
print("IAAS CHARACTERISTICS")
print("=" * 80)

iaas_advantages = [
    "High level of infrastructure control",
    "Flexible operating system selection",
    "Custom software installation",
    "Elastic resource allocation",
    "Suitable for complex infrastructure requirements",
    "Reduced need to purchase physical hardware",
    "Supports migration of traditional applications"
]

for advantage in iaas_advantages:
    print(f"- {advantage}")


print("""
The primary trade-off is that customers remain responsible for substantial
operational work.

For example, creating a virtual machine does not automatically eliminate the
need to secure the operating system running inside it.
""")


# =============================================================================
# 8. PLATFORM AS A SERVICE - PAAS
# =============================================================================

print("\n" + "=" * 80)
print("PLATFORM AS A SERVICE - PAAS")
print("=" * 80)

print("""
Platform as a Service provides a managed environment for developing,
deploying, and operating applications.

The provider manages more of the technology stack than in IaaS.

Instead of manually managing virtual machines and operating systems, the
customer focuses primarily on:

    - Application code
    - Application configuration
    - Data

The platform generally manages infrastructure, operating systems, runtime
components, and many platform-level services.
""")


paas = CloudServiceModel(
    name="Platform as a Service (PaaS)",
    provider_managed=[
        "Networking",
        "Storage",
        "Servers",
        "Virtualization",
        "Operating system",
        "Runtime environment",
        "Middleware",
        "Platform maintenance",
        "Infrastructure scaling mechanisms"
    ],
    customer_managed=[
        "Application code",
        "Application configuration",
        "Application data",
        "User access configuration",
        "Application-level security"
    ]
)

paas.display_responsibilities()


# =============================================================================
# 9. PAAS DEPLOYMENT SIMULATION
# =============================================================================

class PlatformApplication:
    """
    Simulates an application deployed to a managed application platform.
    """

    def __init__(self, name, language, version):
        self.name = name
        self.language = language
        self.version = version
        self.deployment_status = "Not Deployed"

    def deploy(self):
        self.deployment_status = "Running"
        print(
            f"Application '{self.name}' deployed using "
            f"{self.language} {self.version}."
        )

    def display_status(self):
        print(f"Application: {self.name}")
        print(f"Runtime: {self.language} {self.version}")
        print(f"Status: {self.deployment_status}")


print("\nPaaS Example")

application = PlatformApplication(
    name="student-portal",
    language="Python",
    version="3.x"
)

application.deploy()
application.display_status()


print("""
The customer provides the application.

The platform manages the environment required to execute it.

This removes many responsibilities associated with:

    - Server provisioning
    - Operating system administration
    - Runtime installation
    - Infrastructure maintenance
    - Hardware replacement

PaaS is commonly used when development teams want to concentrate more on
application development than infrastructure administration.
""")


# =============================================================================
# 10. PAAS LIMITATIONS AND PECULIARITIES
# =============================================================================

print("=" * 80)
print("PAAS LIMITATIONS")
print("=" * 80)

paas_limitations = [
    "Less infrastructure control than IaaS",
    "Platform-specific constraints",
    "Potential vendor lock-in",
    "Limited operating system customization",
    "Restrictions on supported runtimes",
    "Platform deployment conventions"
]

for limitation in paas_limitations:
    print(f"- {limitation}")


print("""
Vendor lock-in can occur when an application becomes highly dependent on
services or features specific to one cloud platform.

Portability is therefore an important architectural consideration.

An application that uses standard technologies and clearly separated
dependencies is generally easier to migrate than one tightly coupled to
provider-specific services.
""")


# =============================================================================
# 11. SOFTWARE AS A SERVICE - SAAS
# =============================================================================

print("\n" + "=" * 80)
print("SOFTWARE AS A SERVICE - SAAS")
print("=" * 80)

print("""
Software as a Service delivers complete applications to users.

The provider manages nearly the entire technology stack.

The customer generally uses the application through:

    - A web browser
    - A mobile application
    - An application programming interface

The customer does not normally manage:

    - Servers
    - Operating systems
    - Runtime environments
    - Application deployment
    - Core application maintenance

The customer's responsibilities are primarily related to data, users, access,
configuration, and appropriate use of the service.
""")


saas = CloudServiceModel(
    name="Software as a Service (SaaS)",
    provider_managed=[
        "Networking",
        "Storage",
        "Servers",
        "Virtualization",
        "Operating system",
        "Middleware",
        "Runtime",
        "Application infrastructure",
        "Core application software",
        "Application maintenance",
        "Software updates"
    ],
    customer_managed=[
        "Business data",
        "User accounts",
        "Access permissions",
        "Application configuration",
        "Data classification",
        "Appropriate use of the service"
    ]
)

saas.display_responsibilities()


# =============================================================================
# 12. SAAS EXAMPLE
# =============================================================================

class SaaSApplication:
    """
    Represents a customer using a managed software application.
    """

    def __init__(self, application_name):
        self.application_name = application_name
        self.users = []

    def add_user(self, username):
        self.users.append(username)
        print(f"User '{username}' added to {self.application_name}.")

    def list_users(self):
        print(f"\nUsers of {self.application_name}:")
        for user in self.users:
            print(f"- {user}")


print("\nSaaS Example")

business_application = SaaSApplication("Business Collaboration Platform")

business_application.add_user("administrator")
business_application.add_user("employee_01")
business_application.add_user("employee_02")

business_application.list_users()


print("""
The SaaS provider operates the application.

The customer remains responsible for decisions such as:

    - Who should have access?
    - What permissions should each user receive?
    - Which data should be stored?
    - How should sensitive data be classified?
    - Which application settings should be enabled?

The fact that infrastructure is managed by a provider does not remove the
customer's responsibility for data governance and access management.
""")


# =============================================================================
# 13. FUNCTION AS A SERVICE - FAAS
# =============================================================================

print("\n" + "=" * 80)
print("FUNCTION AS A SERVICE - FAAS")
print("=" * 80)

print("""
Function as a Service is a cloud computing model in which developers deploy
individual units of executable logic called functions.

Functions are typically triggered by events.

Examples of events include:

    - An HTTP request
    - A file upload
    - A database modification
    - A message arriving in a queue
    - A scheduled event
    - An event generated by another cloud service

The provider manages infrastructure and usually manages the execution
environment required to run the function.

The customer focuses primarily on:

    - Function code
    - Function configuration
    - Data
    - Event definitions
    - Access permissions
""")


faas = CloudServiceModel(
    name="Function as a Service (FaaS)",
    provider_managed=[
        "Networking",
        "Storage infrastructure",
        "Servers",
        "Virtualization",
        "Operating system",
        "Runtime infrastructure",
        "Function execution environment",
        "Automatic infrastructure provisioning",
        "Infrastructure scaling",
        "Server management"
    ],
    customer_managed=[
        "Function code",
        "Function configuration",
        "Application logic",
        "Data",
        "Event definitions",
        "Access permissions",
        "Dependency management within supported constraints"
    ]
)

faas.display_responsibilities()


# =============================================================================
# 14. FAAS EVENT-DRIVEN EXAMPLE
# =============================================================================

print("\n" + "=" * 80)
print("FAAS EVENT-DRIVEN EXECUTION")
print("=" * 80)


def process_uploaded_file(event):
    """
    Simulates a function triggered when a file is uploaded.
    """

    file_name = event.get("file_name")
    file_size = event.get("file_size")

    print(f"Processing uploaded file: {file_name}")
    print(f"File size: {file_size} MB")

    return {
        "status": "processed",
        "file": file_name
    }


upload_event = {
    "file_name": "financial_report.csv",
    "file_size": 24
}

result = process_uploaded_file(upload_event)

print("Function Result:")
print(result)


print("""
The important distinction is that the developer does not manually provision a
server for every execution.

The cloud platform can allocate execution resources when an event occurs.

After execution:

    - Resources may become idle.
    - Resources may be released.
    - Another execution may receive a separate environment.
    - Scaling may occur automatically if event volume increases.

This model is particularly useful for workloads with irregular or
event-driven execution patterns.
""")


# =============================================================================
# 15. STATELESSNESS IN FAAS
# =============================================================================

print("=" * 80)
print("STATELESSNESS AND FAAS")
print("=" * 80)

print("""
FaaS applications are commonly designed around stateless execution.

A stateless function should not depend on local memory from a previous
execution.

For example, this assumption is unsafe:

    "The same function instance will always process my next request."

The platform may:

    - Reuse an existing execution environment.
    - Create a new environment.
    - Run multiple instances simultaneously.
    - Terminate an existing environment.

Persistent state should therefore usually be stored in an external system
such as:

    - A database
    - Object storage
    - A distributed cache
    - A managed state service
""")


# =============================================================================
# 16. FAAS COLD STARTS
# =============================================================================

print("=" * 80)
print("FAAS COLD STARTS")
print("=" * 80)

print("""
A cold start occurs when a cloud provider needs to initialize a new execution
environment before running a function.

Initialization may involve:

    - Allocating resources
    - Starting a runtime
    - Loading dependencies
    - Initializing application code

This can introduce additional latency.

A warm execution environment may already exist and can execute a request more
quickly.

Cold start behavior depends on multiple factors, including:

    - Runtime technology
    - Package size
    - Dependency size
    - Initialization logic
    - Platform configuration
    - Network configuration

Cold starts demonstrate an important characteristic of highly abstract cloud
services: infrastructure management is simplified for the customer, but
developers still need to understand the operational behavior of the platform.
""")


# =============================================================================
# 17. FAAS CONCURRENCY SIMULATION
# =============================================================================

class FunctionExecution:
    """
    Represents an individual serverless function execution.
    """

    def __init__(self, execution_id, event):
        self.execution_id = execution_id
        self.event = event

    def execute(self):
        print(
            f"Execution {self.execution_id} processing event: "
            f"{self.event}"
        )


events = [
    "file_uploaded",
    "payment_received",
    "database_updated",
    "user_registered"
]

executions = []

for index, event in enumerate(events, start=1):
    execution = FunctionExecution(
        execution_id=index,
        event=event
    )

    executions.append(execution)


print("\nSimulated Concurrent Function Executions:")

for execution in executions:
    execution.execute()


# =============================================================================
# 18. COMPARISON OF ALL SERVICE MODELS
# =============================================================================

print("\n" + "=" * 80)
print("SERVICE MODEL COMPARISON")
print("=" * 80)


service_models = {
    "IaaS": {
        "Provider Manages": [
            "Networking",
            "Storage",
            "Servers",
            "Virtualization"
        ],
        "Customer Focus": [
            "Operating systems",
            "Application environments",
            "Applications",
            "Data"
        ],
        "Control": "High",
        "Infrastructure Management": "High customer responsibility"
    },

    "PaaS": {
        "Provider Manages": [
            "Infrastructure",
            "Operating systems",
            "Runtime",
            "Middleware"
        ],
        "Customer Focus": [
            "Application development",
            "Application configuration",
            "Data"
        ],
        "Control": "Medium",
        "Infrastructure Management": "Moderate to low customer responsibility"
    },

    "SaaS": {
        "Provider Manages": [
            "Infrastructure",
            "Platform",
            "Application"
        ],
        "Customer Focus": [
            "Data",
            "Users",
            "Configuration"
        ],
        "Control": "Low",
        "Infrastructure Management": "Minimal customer responsibility"
    },

    "FaaS": {
        "Provider Manages": [
            "Infrastructure",
            "Execution environment",
            "Scaling mechanisms"
        ],
        "Customer Focus": [
            "Functions",
            "Events",
            "Business logic",
            "Data"
        ],
        "Control": "Limited infrastructure control",
        "Infrastructure Management": "Minimal server management"
    }
}


for model_name, details in service_models.items():

    print("\n" + "-" * 60)
    print(model_name)
    print("-" * 60)

    print("Provider Manages:")
    for item in details["Provider Manages"]:
        print(f"  - {item}")

    print("Customer Focus:")
    for item in details["Customer Focus"]:
        print(f"  - {item}")

    print(f"Control Level: {details['Control']}")
    print(
        f"Infrastructure Management: "
        f"{details['Infrastructure Management']}"
    )


# =============================================================================
# 19. RESPONSIBILITY MATRIX
# =============================================================================

print("\n" + "=" * 80)
print("RESPONSIBILITY MATRIX")
print("=" * 80)


responsibility_matrix = {
    "Networking": {
        "IaaS": "Provider",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Storage Infrastructure": {
        "IaaS": "Provider",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Physical Servers": {
        "IaaS": "Provider",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Virtualization": {
        "IaaS": "Provider",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Operating System": {
        "IaaS": "Customer",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Runtime": {
        "IaaS": "Customer",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Middleware": {
        "IaaS": "Customer",
        "PaaS": "Provider",
        "SaaS": "Provider",
        "FaaS": "Provider"
    },

    "Application": {
        "IaaS": "Customer",
        "PaaS": "Customer",
        "SaaS": "Provider",
        "FaaS": "Customer"
    },

    "Data": {
        "IaaS": "Customer",
        "PaaS": "Customer",
        "SaaS": "Customer",
        "FaaS": "Customer"
    }
}


header = (
    f"{'Layer':<25}"
    f"{'IaaS':<15}"
    f"{'PaaS':<15}"
    f"{'SaaS':<15}"
    f"{'FaaS':<15}"
)

print(header)
print("-" * 85)

for layer, responsibility in responsibility_matrix.items():

    print(
        f"{layer:<25}"
        f"{responsibility['IaaS']:<15}"
        f"{responsibility['PaaS']:<15}"
        f"{responsibility['SaaS']:<15}"
        f"{responsibility['FaaS']:<15}"
    )


# =============================================================================
# 20. IMPORTANT SHARED RESPONSIBILITY PECULIARITY
# =============================================================================

print("\n" + "=" * 80)
print("INFRASTRUCTURE RESPONSIBILITY VS DATA RESPONSIBILITY")
print("=" * 80)

print("""
A common misunderstanding is that moving to a more managed cloud service
transfers all security responsibility to the cloud provider.

This is incorrect.

For example:

The provider may secure:
    - Data centers
    - Physical servers
    - Networking infrastructure
    - Managed platform components

The customer may still be responsible for:
    - User access permissions
    - Password policies
    - Identity management
    - Data classification
    - Sensitive data exposure
    - Application configuration
    - API access
    - Encryption configuration where applicable

The responsibility boundary changes, but responsibility does not disappear.
""")


# =============================================================================
# 21. SECURITY RESPONSIBILITIES BY MODEL
# =============================================================================

security_responsibilities = {
    "IaaS": [
        "Secure virtual machines",
        "Patch operating systems",
        "Configure firewalls",
        "Secure applications",
        "Protect credentials",
        "Manage user access",
        "Protect data"
    ],

    "PaaS": [
        "Secure application code",
        "Manage application access",
        "Protect application secrets",
        "Secure application configuration",
        "Protect data"
    ],

    "SaaS": [
        "Manage users",
        "Configure permissions",
        "Protect business data",
        "Control sharing",
        "Configure available security features"
    ],

    "FaaS": [
        "Secure function code",
        "Manage function permissions",
        "Protect secrets",
        "Validate event input",
        "Protect data"
    ]
}


print("=" * 80)
print("SECURITY RESPONSIBILITIES")
print("=" * 80)

for model, responsibilities in security_responsibilities.items():

    print(f"\n{model}")

    for responsibility in responsibilities:
        print(f"  - {responsibility}")


# =============================================================================
# 22. SCALABILITY
# =============================================================================

print("\n" + "=" * 80)
print("SCALABILITY ACROSS CLOUD SERVICE MODELS")
print("=" * 80)

print("""
Scalability refers to the ability of a system to handle changes in workload.

The responsibility for scaling changes according to the cloud service model.

IaaS:
    Customers may need to configure virtual machine capacity, load balancing,
    autoscaling, and infrastructure monitoring.

PaaS:
    The platform may provide managed scaling mechanisms, reducing direct
    infrastructure administration.

SaaS:
    The provider manages application infrastructure scaling.

FaaS:
    Functions can often scale based on event volume, subject to platform
    concurrency and quota constraints.
""")


# =============================================================================
# 23. COST MODEL DIFFERENCES
# =============================================================================

print("=" * 80)
print("COST CHARACTERISTICS")
print("=" * 80)

cost_models = {
    "IaaS": """
Resources are commonly associated with provisioned infrastructure capacity.
Idle resources can continue generating costs depending on configuration.
""",

    "PaaS": """
Costs are associated with managed platform resources and application capacity.
The customer pays for the platform abstraction rather than directly managing
every infrastructure component.
""",

    "SaaS": """
Costs are often subscription-based and may depend on users, features, storage,
or usage levels.
""",

    "FaaS": """
Costs are commonly associated with execution-related factors such as request
volume, execution duration, memory allocation, and related services.
"""
}


for model, description in cost_models.items():
    print(f"\n{model}")
    print(description.strip())


# =============================================================================
# 24. CONTROL VS ABSTRACTION
# =============================================================================

print("\n" + "=" * 80)
print("CONTROL VS ABSTRACTION")
print("=" * 80)

print("""
Cloud service models exist on a spectrum.

More infrastructure control generally means:

    - More customization
    - More operational responsibility
    - More configuration requirements
    - More maintenance responsibility

More abstraction generally means:

    - Less infrastructure administration
    - Faster consumption of managed services
    - More provider-managed components
    - Reduced low-level customization

A simplified conceptual relationship is:

    Higher Control
        IaaS
          |
          |
        PaaS
          |
          |
        FaaS
          |
          |
        SaaS
    Higher Abstraction

This relationship is not perfectly linear because FaaS and PaaS serve different
architectural purposes. Both provide higher abstraction than IaaS, but FaaS
is specifically oriented around event-driven execution.
""")


# =============================================================================
# 25. IAAS VS PAAS
# =============================================================================

print("=" * 80)
print("IAAS VS PAAS")
print("=" * 80)

print("""
IaaS provides infrastructure building blocks.

PaaS provides an environment for application development and execution.

With IaaS:

    The customer may create a virtual machine.
    The customer installs the operating system.
    The customer installs Python.
    The customer installs dependencies.
    The customer deploys the application.
    The customer manages server maintenance.

With PaaS:

    The customer provides application code.
    The platform provides the execution environment.
    The platform manages much of the underlying infrastructure.

The choice depends largely on the amount of infrastructure control required.
""")


# =============================================================================
# 26. PAAS VS FAAS
# =============================================================================

print("=" * 80)
print("PAAS VS FAAS")
print("=" * 80)

print("""
PaaS generally provides an environment for continuously running applications.

FaaS generally executes code in response to specific events.

PaaS applications may include:

    - Web applications
    - APIs
    - Long-running application services

FaaS workloads may include:

    - File processing
    - Event processing
    - Notifications
    - Data transformation
    - Scheduled tasks
    - API handlers

A major architectural distinction is execution lifecycle.

A PaaS application can remain active continuously.

A FaaS function is typically invoked when required.
""")


# =============================================================================
# 27. FAAS VS SAAS
# =============================================================================

print("=" * 80)
print("FAAS VS SAAS")
print("=" * 80)

print("""
FaaS is a development and execution model.

SaaS is a software consumption model.

With FaaS:

    Developers write and deploy application logic.

With SaaS:

    Users consume a complete application.

Therefore, these models operate at different levels of abstraction and serve
different audiences.
""")


# =============================================================================
# 28. WORKLOAD SELECTION
# =============================================================================

class Workload:
    """
    Represents a workload with characteristics that can influence the choice
    of cloud service model.
    """

    def __init__(
        self,
        name,
        requires_os_control,
        custom_infrastructure,
        application_development,
        event_driven,
        ready_made_software
    ):
        self.name = name
        self.requires_os_control = requires_os_control
        self.custom_infrastructure = custom_infrastructure
        self.application_development = application_development
        self.event_driven = event_driven
        self.ready_made_software = ready_made_software

    def recommend_model(self):

        if self.ready_made_software:
            return "SaaS"

        if self.event_driven:
            return "FaaS"

        if self.requires_os_control or self.custom_infrastructure:
            return "IaaS"

        if self.application_development:
            return "PaaS"

        return "Architecture assessment required"


workloads = [
    Workload(
        name="Legacy enterprise application",
        requires_os_control=True,
        custom_infrastructure=True,
        application_development=True,
        event_driven=False,
        ready_made_software=False
    ),

    Workload(
        name="Web application",
        requires_os_control=False,
        custom_infrastructure=False,
        application_development=True,
        event_driven=False,
        ready_made_software=False
    ),

    Workload(
        name="File upload processing",
        requires_os_control=False,
        custom_infrastructure=False,
        application_development=True,
        event_driven=True,
        ready_made_software=False
    ),

    Workload(
        name="Business productivity application",
        requires_os_control=False,
        custom_infrastructure=False,
        application_development=False,
        event_driven=False,
        ready_made_software=True
    )
]


print("\n" + "=" * 80)
print("WORKLOAD SERVICE MODEL SELECTION")
print("=" * 80)

for workload in workloads:
    recommendation = workload.recommend_model()

    print(f"\nWorkload: {workload.name}")
    print(f"Recommended Model: {recommendation}")


# =============================================================================
# 29. MULTI-MODEL CLOUD ARCHITECTURES
# =============================================================================

print("\n" + "=" * 80)
print("MULTI-MODEL CLOUD ARCHITECTURES")
print("=" * 80)

print("""
Organizations do not need to select only one cloud service model.

A single architecture can use multiple models.

For example:

    IaaS:
        A specialized legacy system requiring operating system control.

    PaaS:
        A custom web application.

    FaaS:
        Event-driven background processing.

    SaaS:
        Business collaboration and productivity software.

This means cloud service models are often complementary rather than mutually
exclusive.
""")


# =============================================================================
# 30. RESPONSIBILITY DECISION FRAMEWORK
# =============================================================================

print("=" * 80)
print("RESPONSIBILITY DECISION FRAMEWORK")
print("=" * 80)


questions = [
    (
        "Do you require direct operating system administration?",
        "IaaS may be appropriate."
    ),

    (
        "Do you primarily want to develop and deploy applications?",
        "PaaS may be appropriate."
    ),

    (
        "Do you need complete software without developing infrastructure?",
        "SaaS may be appropriate."
    ),

    (
        "Is the workload triggered by independent events?",
        "FaaS may be appropriate."
    ),

    (
        "Do you require extensive infrastructure customization?",
        "IaaS provides greater infrastructure control."
    ),

    (
        "Do you want to minimize server administration?",
        "PaaS or FaaS may reduce operational responsibility."
    )
]


for question, interpretation in questions:
    print(f"\nQuestion: {question}")
    print(f"Interpretation: {interpretation}")


# =============================================================================
# 31. ADVANCED CONSIDERATION: VENDOR LOCK-IN
# =============================================================================

print("\n" + "=" * 80)
print("VENDOR LOCK-IN")
print("=" * 80)

print("""
Vendor lock-in refers to the difficulty of moving an application or workload
from one provider to another.

Lock-in can result from:

    - Provider-specific APIs
    - Proprietary databases
    - Platform-specific deployment mechanisms
    - Proprietary event systems
    - Specialized managed services
    - Custom identity systems

Managed services can provide significant operational advantages, but
architectural decisions should account for portability requirements.

The objective is not necessarily to avoid every provider-specific service.

Instead, the appropriate level of dependency should be considered based on:

    - Business requirements
    - Migration costs
    - Operational benefits
    - Regulatory requirements
    - Long-term architecture
""")


# =============================================================================
# 32. ADVANCED CONSIDERATION: OBSERVABILITY
# =============================================================================

print("=" * 80)
print("OBSERVABILITY")
print("=" * 80)

print("""
The level of cloud abstraction affects how systems are monitored.

IaaS monitoring may include:

    - CPU utilization
    - Memory utilization
    - Disk utilization
    - Operating system logs
    - Network traffic

PaaS monitoring may focus more heavily on:

    - Application performance
    - Requests
    - Errors
    - Response times
    - Platform metrics

FaaS monitoring may include:

    - Invocation count
    - Execution duration
    - Error count
    - Timeout rate
    - Cold start behavior
    - Concurrency

SaaS monitoring is generally focused on:

    - User activity
    - Application usage
    - Audit logs
    - Configuration
    - Service availability
""")


# =============================================================================
# 33. ADVANCED CONSIDERATION: FAILURE DOMAINS
# =============================================================================

print("=" * 80)
print("FAILURE DOMAINS")
print("=" * 80)

print("""
Cloud architectures should distinguish between responsibility and dependency.

Even when a provider manages infrastructure, applications can still fail
because of:

    - Incorrect application code
    - Invalid configuration
    - Dependency failures
    - Permission errors
    - Network connectivity problems
    - Data corruption
    - External service failures

Higher abstraction reduces certain operational responsibilities but does not
eliminate distributed system complexity.
""")


# =============================================================================
# 34. ADVANCED CONSIDERATION: SECURITY CONFIGURATION
# =============================================================================

print("=" * 80)
print("CONFIGURATION AS A SECURITY BOUNDARY")
print("=" * 80)

print("""
Managed cloud services are frequently configured through permissions,
policies, identities, and network rules.

A service can be technically secure at the infrastructure level while still
being exposed because of incorrect customer configuration.

Examples include:

    - Excessively broad permissions
    - Publicly exposed resources
    - Weak authentication
    - Poor secret management
    - Incorrect data sharing policies
    - Unrestricted API access

Cloud security therefore depends not only on who manages infrastructure but
also on how customers configure the services they consume.
""")


# =============================================================================
# 35. FINAL RESPONSIBILITY VISUALIZATION
# =============================================================================

print("=" * 80)
print("RESPONSIBILITY PROGRESSION")
print("=" * 80)

responsibility_scale = [
    ("IaaS", "Customer manages many software and configuration layers."),
    ("PaaS", "Customer focuses mainly on applications and data."),
    ("FaaS", "Customer focuses on event-driven application logic and data."),
    ("SaaS", "Customer primarily manages users, configuration, and data.")
]

for model, explanation in responsibility_scale:
    print(f"{model:<10} -> {explanation}")


print("""
The defining characteristic of cloud service models is not simply where an
application runs.

The defining characteristic is the division of responsibility.

IaaS transfers physical infrastructure responsibility while preserving
significant customer control.

PaaS transfers infrastructure and platform management responsibilities while
allowing customers to develop and operate applications.

SaaS delivers complete software and leaves customers primarily responsible for
their users, configuration, access controls, and data.

FaaS abstracts server management and executes application logic in response
to events, allowing developers to focus on individual functions and their
associated business logic.

The service model selected for a workload determines the boundaries of
operational control, customization, maintenance, security responsibility,
deployment practices, scalability mechanisms, and cost behavior.
""")
