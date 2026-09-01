# Cloud Computing Infrastructure Learning Journey – 120 Day Roadmap

## Overview

This 120-day learning journey is designed to build a strong understanding of **Cloud Computing and Infrastructure** from beginner to advanced level. The roadmap covers cloud fundamentals, Linux, networking, virtualization, cloud platforms, compute, storage, databases, security, containers, Docker, Kubernetes, Infrastructure as Code, CI/CD, monitoring, reliability engineering, distributed systems, and enterprise-scale infrastructure.

| Phase    |    Days | Focus Area                                                 |
| -------- | ------: | ---------------------------------------------------------- |
| Phase 1  |    1–10 | Introduction to Cloud Computing                            |
| Phase 2  |   11–20 | Linux and Operating System Fundamentals                    |
| Phase 3  |   21–30 | Networking Fundamentals                                    |
| Phase 4  |   31–40 | Virtualization and Cloud Infrastructure                    |
| Phase 5  |   41–55 | Cloud Compute and Storage                                  |
| Phase 6  |   56–65 | Databases and Cloud Data Infrastructure                    |
| Phase 7  |   66–75 | Cloud Security and Identity                                |
| Phase 8  |   76–85 | Containers and Docker                                      |
| Phase 9  |   86–95 | Kubernetes and Container Orchestration                     |
| Phase 10 |  96–105 | Infrastructure as Code and Automation                      |
| Phase 11 | 106–112 | DevOps, CI/CD and Observability                            |
| Phase 12 | 113–120 | Advanced Cloud Architecture and Infrastructure Engineering |

# Phase 1: Cloud Computing Fundamentals

| Day | Topic                               | Detailed Learning Objectives                                                                                                                        |
| --: | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
|   1 | Introduction to Cloud Computing     | Understand cloud computing, its evolution, traditional infrastructure vs cloud infrastructure, and the reasons organizations adopt cloud platforms. |
|   2 | History of Computing Infrastructure | Learn about mainframes, client-server architecture, data centers, virtualization, distributed computing, and the evolution toward cloud computing.  |
|   3 | Cloud Computing Characteristics     | Study on-demand self-service, broad network access, resource pooling, rapid elasticity, and measured service.                                       |
|   4 | Cloud Service Models                | Understand IaaS, PaaS, SaaS, FaaS, and compare responsibilities between cloud providers and customers.                                              |
|   5 | Cloud Deployment Models             | Learn public cloud, private cloud, hybrid cloud, multi-cloud, and community cloud architectures.                                                    |
|   6 | Benefits of Cloud Computing         | Study scalability, elasticity, availability, global infrastructure, cost optimization, automation, and disaster recovery.                           |
|   7 | Cloud Computing Challenges          | Learn about vendor lock-in, latency, security concerns, compliance, outages, data residency, and cost management.                                   |
|   8 | Cloud Providers Overview            | Explore major cloud providers and understand their core infrastructure services and global architecture.                                            |
|   9 | Cloud Infrastructure Components     | Study servers, storage, networking, virtualization, hypervisors, data centers, regions, and availability zones.                                     |
|  10 | Cloud Architecture Fundamentals     | Understand how compute, networking, storage, security, and applications work together in a cloud environment.                                       |

# Phase 2: Linux and Operating System Fundamentals

| Day | Topic                              | Detailed Learning Objectives                                                                                 |
| --: | ---------------------------------- | ------------------------------------------------------------------------------------------------------------ |
|  11 | Introduction to Linux              | Understand Linux architecture, distributions, kernels, shells, and why Linux dominates cloud infrastructure. |
|  12 | Linux Installation and Environment | Learn virtual machines, cloud Linux instances, terminal environments, SSH access, and remote administration. |
|  13 | Linux File System                  | Study directories, paths, files, permissions, ownership, symbolic links, and the Linux filesystem hierarchy. |
|  14 | Linux Commands                     | Practice navigation, file creation, copying, moving, deleting, searching, and inspecting files.              |
|  15 | Users and Groups                   | Learn user accounts, groups, permissions, sudo access, authentication, and privilege management.             |
|  16 | Processes and Services             | Understand processes, threads, process monitoring, signals, system services, and systemd.                    |
|  17 | Package Management                 | Learn package managers, repositories, software installation, updates, dependencies, and version management.  |
|  18 | Linux Networking                   | Study network interfaces, IP addresses, DNS configuration, routing basics, and network troubleshooting.      |
|  19 | Shell Scripting                    | Learn Bash fundamentals, variables, conditions, loops, functions, arguments, and automation scripts.         |
|  20 | Linux Administration Project       | Configure a Linux server with users, SSH access, permissions, packages, services, and automated scripts.     |

# Phase 3: Networking Fundamentals

| Day | Topic                               | Detailed Learning Objectives                                                                          |
| --: | ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
|  21 | Introduction to Computer Networking | Understand network communication, clients, servers, protocols, packets, and network infrastructure.   |
|  22 | OSI Model                           | Study all seven layers and understand how networking protocols operate across layers.                 |
|  23 | TCP/IP Model                        | Learn application, transport, internet, and network access layers.                                    |
|  24 | IP Addressing                       | Understand IPv4, IPv6, public IPs, private IPs, and address allocation.                               |
|  25 | Subnetting                          | Learn CIDR notation, subnet masks, network ranges, hosts, and subnet calculations.                    |
|  26 | TCP and UDP                         | Compare connection-oriented and connectionless communication and understand common use cases.         |
|  27 | DNS                                 | Learn domain names, DNS resolution, records, recursive resolvers, authoritative servers, and caching. |
|  28 | HTTP and HTTPS                      | Understand web communication, requests, responses, TLS, certificates, and secure communication.       |
|  29 | Routing and NAT                     | Study routers, routing tables, gateways, NAT, internet gateways, and packet forwarding.               |
|  30 | Load Balancing                      | Learn Layer 4 and Layer 7 load balancing, health checks, traffic distribution, and high availability. |

# Phase 4: Virtualization and Cloud Infrastructure

| Day | Topic                          | Detailed Learning Objectives                                                                                  |
| --: | ------------------------------ | ------------------------------------------------------------------------------------------------------------- |
|  31 | Introduction to Virtualization | Understand physical servers, virtual machines, resource abstraction, and virtualization benefits.             |
|  32 | Hypervisors                    | Learn Type 1 and Type 2 hypervisors and how virtual machines are created and managed.                         |
|  33 | Virtual Machines               | Study CPU, memory, disk, networking, images, snapshots, and VM lifecycle management.                          |
|  34 | Server Virtualization          | Understand how physical hardware resources are divided among multiple virtual environments.                   |
|  35 | Storage Virtualization         | Learn logical volumes, virtual disks, block storage abstraction, and storage pools.                           |
|  36 | Network Virtualization         | Study virtual networks, virtual switches, software-defined networking, and network overlays.                  |
|  37 | Containers vs Virtual Machines | Compare containers and VMs in terms of isolation, performance, portability, and resource usage.               |
|  38 | Data Centers                   | Understand racks, servers, cooling, power systems, redundancy, and physical infrastructure.                   |
|  39 | Regions and Availability Zones | Learn geographic infrastructure design and fault isolation strategies.                                        |
|  40 | Cloud Infrastructure Project   | Design a basic virtual cloud infrastructure containing compute, networking, storage, and security components. |

# Phase 5: Cloud Compute and Storage

| Day | Topic                       | Detailed Learning Objectives                                                                                  |
| --: | --------------------------- | ------------------------------------------------------------------------------------------------------------- |
|  41 | Cloud Compute Fundamentals  | Understand cloud instances, virtual CPUs, memory, instance families, and compute provisioning.                |
|  42 | Virtual Server Deployment   | Launch and configure cloud virtual machines and understand instance lifecycle management.                     |
|  43 | Auto Scaling                | Learn horizontal scaling, vertical scaling, scaling policies, and automated infrastructure expansion.         |
|  44 | Serverless Computing        | Understand functions, event-driven execution, scaling, and serverless architecture.                           |
|  45 | Cloud Storage Fundamentals  | Learn storage concepts including durability, availability, redundancy, and replication.                       |
|  46 | Object Storage              | Study buckets, objects, metadata, lifecycle policies, versioning, and object storage architecture.            |
|  47 | Block Storage               | Learn volumes, disks, snapshots, performance characteristics, and compute attachment.                         |
|  48 | File Storage                | Understand shared file systems, network file storage, and distributed storage systems.                        |
|  49 | Storage Performance         | Study IOPS, throughput, latency, caching, storage tiers, and performance optimization.                        |
|  50 | Data Backup                 | Learn full backups, incremental backups, snapshots, retention policies, and backup automation.                |
|  51 | Disaster Recovery           | Understand RPO, RTO, backup recovery, pilot light, warm standby, and multi-region recovery.                   |
|  52 | Content Delivery Networks   | Learn edge locations, caching, content distribution, and latency reduction.                                   |
|  53 | Cloud Load Balancers        | Configure traffic routing, health checks, SSL termination, and backend target groups.                         |
|  54 | Cloud Scaling Architecture  | Design an infrastructure using load balancers, auto scaling, and distributed compute.                         |
|  55 | Compute and Storage Project | Build a scalable application architecture using virtual servers, object storage, backups, and load balancing. |

# Phase 6: Databases and Cloud Data Infrastructure

| Day | Topic                                | Detailed Learning Objectives                                                                         |
| --: | ------------------------------------ | ---------------------------------------------------------------------------------------------------- |
|  56 | Database Infrastructure Fundamentals | Understand database servers, storage engines, transactions, replication, and availability.           |
|  57 | Relational Databases                 | Learn SQL databases, schemas, tables, indexes, transactions, and relational architecture.            |
|  58 | Managed Database Services            | Understand cloud-managed databases and automated patching, backups, scaling, and replication.        |
|  59 | Database Replication                 | Learn primary-replica architecture, synchronous replication, asynchronous replication, and failover. |
|  60 | Database High Availability           | Study clustering, multi-zone databases, automatic failover, and redundancy.                          |
|  61 | NoSQL Databases                      | Learn key-value, document, wide-column, and graph database architectures.                            |
|  62 | Database Scaling                     | Understand vertical scaling, horizontal scaling, partitioning, and sharding.                         |
|  63 | Caching Systems                      | Learn in-memory caching, distributed caches, cache invalidation, and caching strategies.             |
|  64 | Data Warehousing                     | Understand analytical databases, ETL pipelines, OLTP vs OLAP, and data infrastructure.               |
|  65 | Database Infrastructure Project      | Design a highly available database architecture with backups, replicas, caching, and monitoring.     |

# Phase 7: Cloud Security and Identity

| Day | Topic                            | Detailed Learning Objectives                                                                        |
| --: | -------------------------------- | --------------------------------------------------------------------------------------------------- |
|  66 | Cloud Security Fundamentals      | Understand the shared responsibility model and cloud security principles.                           |
|  67 | Identity and Access Management   | Learn users, groups, roles, policies, permissions, and least privilege.                             |
|  68 | Authentication and Authorization | Understand passwords, MFA, tokens, OAuth concepts, and access control.                              |
|  69 | Network Security                 | Learn firewalls, security groups, network ACLs, and traffic filtering.                              |
|  70 | Encryption                       | Study encryption at rest, encryption in transit, symmetric encryption, and public-key cryptography. |
|  71 | Key Management                   | Learn encryption keys, key rotation, secrets management, and hardware security concepts.            |
|  72 | Cloud Security Monitoring        | Study logs, audit trails, security alerts, anomaly detection, and incident investigation.           |
|  73 | Vulnerability Management         | Learn vulnerability scanning, patching, CVEs, dependency risks, and remediation processes.          |
|  74 | Compliance and Governance        | Understand data privacy, regulatory compliance, auditing, policies, and governance frameworks.      |
|  75 | Cloud Security Project           | Secure a cloud infrastructure using IAM, network isolation, encryption, logging, and monitoring.    |

# Phase 8: Containers and Docker

| Day | Topic                      | Detailed Learning Objectives                                                                                   |
| --: | -------------------------- | -------------------------------------------------------------------------------------------------------------- |
|  76 | Introduction to Containers | Understand containerization, isolation, portability, and application packaging.                                |
|  77 | Docker Fundamentals        | Learn Docker architecture, images, containers, registries, and basic commands.                                 |
|  78 | Docker Images              | Study image layers, Dockerfiles, image optimization, and build processes.                                      |
|  79 | Docker Containers          | Learn container lifecycle, networking, environment variables, volumes, and execution.                          |
|  80 | Docker Networking          | Understand bridge networks, host networking, container communication, and network isolation.                   |
|  81 | Docker Volumes             | Learn persistent storage, bind mounts, volumes, and data management.                                           |
|  82 | Docker Compose             | Build multi-container applications using declarative service configuration.                                    |
|  83 | Container Registries       | Learn image repositories, tagging, versioning, private registries, and image distribution.                     |
|  84 | Container Security         | Study image scanning, minimal images, secrets, runtime security, and vulnerability management.                 |
|  85 | Docker Project             | Containerize a multi-service application with frontend, backend, database, networking, and persistent storage. |

# Phase 9: Kubernetes and Container Orchestration

| Day | Topic                       | Detailed Learning Objectives                                                                  |
| --: | --------------------------- | --------------------------------------------------------------------------------------------- |
|  86 | Introduction to Kubernetes  | Understand container orchestration, clusters, nodes, and Kubernetes architecture.             |
|  87 | Kubernetes Control Plane    | Study API servers, schedulers, controllers, etcd, and control plane operations.               |
|  88 | Pods                        | Learn pods, containers, pod lifecycle, manifests, and workload deployment.                    |
|  89 | Deployments and ReplicaSets | Understand declarative deployments, replicas, rolling updates, and rollbacks.                 |
|  90 | Kubernetes Services         | Learn service discovery, ClusterIP, NodePort, LoadBalancer, and traffic routing.              |
|  91 | ConfigMaps and Secrets      | Manage application configuration, sensitive data, and environment variables.                  |
|  92 | Persistent Storage          | Study PersistentVolumes, PersistentVolumeClaims, StorageClasses, and StatefulSets.            |
|  93 | Kubernetes Networking       | Understand CNI, pod networking, network policies, ingress, and service communication.         |
|  94 | Kubernetes Scaling          | Learn horizontal pod autoscaling, vertical scaling, cluster autoscaling, and resource limits. |
|  95 | Kubernetes Project          | Deploy and manage a scalable multi-service application on Kubernetes.                         |

# Phase 10: Infrastructure as Code and Automation

| Day | Topic                               | Detailed Learning Objectives                                                                                  |
| --: | ----------------------------------- | ------------------------------------------------------------------------------------------------------------- |
|  96 | Infrastructure as Code Fundamentals | Understand declarative infrastructure, automation, reproducibility, and infrastructure version control.       |
|  97 | Terraform Fundamentals              | Learn providers, resources, variables, outputs, state files, and execution workflows.                         |
|  98 | Terraform State Management          | Understand local state, remote state, locking, state security, and collaboration.                             |
|  99 | Terraform Modules                   | Learn reusable infrastructure modules, module composition, and infrastructure abstraction.                    |
| 100 | Advanced Terraform                  | Study dependencies, workspaces, lifecycle management, provisioners, and infrastructure patterns.              |
| 101 | Configuration Management            | Understand infrastructure configuration and server configuration automation.                                  |
| 102 | Automation with Ansible             | Learn inventories, playbooks, roles, variables, templates, and automation workflows.                          |
| 103 | Infrastructure Testing              | Study validation, automated testing, policy checks, and infrastructure security scanning.                     |
| 104 | GitOps Fundamentals                 | Learn infrastructure repositories, declarative operations, pull requests, and automated deployment workflows. |
| 105 | Infrastructure Automation Project   | Build cloud infrastructure using Terraform, configure systems using Ansible, and manage code using Git.       |

# Phase 11: DevOps, CI/CD and Observability

| Day | Topic                        | Detailed Learning Objectives                                                                       |
| --: | ---------------------------- | -------------------------------------------------------------------------------------------------- |
| 106 | DevOps Fundamentals          | Understand collaboration between development and operations and the culture of automation.         |
| 107 | CI/CD Fundamentals           | Learn continuous integration, continuous delivery, pipelines, builds, tests, and deployments.      |
| 108 | CI/CD Pipelines              | Build automated pipelines for testing, building containers, and deploying applications.            |
| 109 | Monitoring Fundamentals      | Understand metrics, monitoring systems, alerts, dashboards, and infrastructure health.             |
| 110 | Logging Systems              | Learn centralized logging, log aggregation, log analysis, and structured logs.                     |
| 111 | Distributed Tracing          | Understand request tracing, microservice observability, latency analysis, and dependency tracking. |
| 112 | Site Reliability Engineering | Learn SLIs, SLOs, SLAs, error budgets, incident response, and reliability engineering.             |

# Phase 12: Advanced Cloud Architecture and Infrastructure Engineering

| Day | Topic                                   | Detailed Learning Objectives                                                                                                                                                                                              |
| --: | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 113 | High Availability Architecture          | Design systems that tolerate failures through redundancy, replication, and automated recovery.                                                                                                                            |
| 114 | Fault-Tolerant Systems                  | Learn failure domains, graceful degradation, retries, circuit breakers, and resilience patterns.                                                                                                                          |
| 115 | Distributed Systems Fundamentals        | Understand distributed computing, consensus, consistency, replication, and network failures.                                                                                                                              |
| 116 | Microservices Infrastructure            | Learn service discovery, API gateways, communication patterns, and infrastructure for microservices.                                                                                                                      |
| 117 | Event-Driven Architecture               | Study message queues, event streams, asynchronous communication, and event processing infrastructure.                                                                                                                     |
| 118 | Multi-Cloud and Hybrid Cloud            | Understand cross-cloud infrastructure, portability, interoperability, and hybrid architectures.                                                                                                                           |
| 119 | Cloud Cost Optimization and FinOps      | Learn cloud billing models, resource optimization, tagging, rightsizing, reserved capacity, and cost governance.                                                                                                          |
| 120 | Enterprise Cloud Infrastructure Project | Design an enterprise-grade infrastructure using networking, compute, containers, Kubernetes, databases, security, Infrastructure as Code, CI/CD, monitoring, disaster recovery, high availability, and cost optimization. |
