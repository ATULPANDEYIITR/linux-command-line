# ============================================================
# DAY 00: LINUX FUNDAMENTALS
# ============================================================

print("DAY 01 - LINUX FUNDAMENTALS")


# ============================================================
# 1. WHAT IS LINUX?
# ============================================================

print("\n1. WHAT IS LINUX?")

print("Linux is an open-source operating system kernel.")
print("Linux-based operating systems are widely used in")
print("servers, cloud infrastructure, cybersecurity,")
print("software development, embedded systems, and desktops.")


# ============================================================
# 2. LINUX DISTRIBUTIONS
# ============================================================

print("\n2. LINUX DISTRIBUTIONS")

distributions = [
    "Ubuntu",
    "Debian",
    "Fedora",
    "Arch Linux",
    "Red Hat Enterprise Linux",
    "Linux Mint"
]

for distribution in distributions:
    print("-", distribution)


# ============================================================
# 3. TERMINAL AND SHELL
# ============================================================

print("\n3. TERMINAL AND SHELL")

print("Terminal -> Interface used to interact with the system")
print("Shell    -> Program that interprets commands")

print("\nCommon shells include:")
print("- Bash")
print("- Zsh")
print("- Fish")


# ============================================================
# 4. BASIC LINUX COMMANDS
# ============================================================

print("\n4. BASIC LINUX COMMANDS")

commands = {
    "pwd": "Show current directory",
    "ls": "List files and directories",
    "cd": "Change directory",
    "mkdir": "Create a directory",
    "touch": "Create a file",
    "cp": "Copy files or directories",
    "mv": "Move or rename files",
    "rm": "Remove files or directories"
}

for command, purpose in commands.items():
    print(command, "->", purpose)


# ============================================================
# 5. LINUX FILESYSTEM
# ============================================================

print("\n5. LINUX FILESYSTEM")

directories = {
    "/": "Root directory",
    "/home": "User home directories",
    "/etc": "System configuration files",
    "/var": "Variable data and logs",
    "/tmp": "Temporary files",
    "/usr": "User programs and utilities",
    "/bin": "Essential executable programs"
}

for directory, purpose in directories.items():
    print(directory, "->", purpose)


# ============================================================
# 6. ABSOLUTE AND RELATIVE PATHS
# ============================================================

print("\n6. ABSOLUTE AND RELATIVE PATHS")

absolute_path = "/home/user/documents/file.txt"
relative_path = "documents/file.txt"

print("Absolute Path:", absolute_path)
print("Relative Path:", relative_path)

print("\nAbsolute paths start from the root directory.")
print("Relative paths are interpreted from the current directory.")


# ============================================================
# 7. FILE TYPES
# ============================================================

print("\n7. FILE TYPES")

file_types = [
    "Regular File",
    "Directory",
    "Symbolic Link",
    "Device File"
]

for file_type in file_types:
    print("-", file_type)


# ============================================================
# 8. FILE PERMISSIONS
# ============================================================

print("\n8. FILE PERMISSIONS")

permissions = {
    "r": "Read",
    "w": "Write",
    "x": "Execute"
}

for permission, meaning in permissions.items():
    print(permission, "->", meaning)

print("\nLinux permissions are commonly represented for:")
print("- Owner")
print("- Group")
print("- Others")


# ============================================================
# 9. EXAMPLE PERMISSION
# ============================================================

print("\n9. EXAMPLE PERMISSION")

permission_string = "rwxr-xr--"

print("Permission:", permission_string)

print("""
Owner  -> rwx
Group  -> r-x
Others -> r--
""")


# ============================================================
# 10. USERS AND GROUPS
# ============================================================

print("\n10. USERS AND GROUPS")

user = {
    "username": "developer",
    "group": "developers"
}

print("Username:", user["username"])
print("Group:", user["group"])

print("\nLinux uses users and groups to manage")
print("ownership and access to system resources.")


# ============================================================
# 11. ROOT USER
# ============================================================

print("\n11. ROOT USER")

print("The root user has extensive administrative privileges.")
print("Administrative commands should be used carefully.")


# ============================================================
# 12. PROCESSES
# ============================================================

print("\n12. PROCESSES")

processes = [
    "Web Server",
    "Database",
    "Background Service",
    "Terminal Shell"
]

for process in processes:
    print("-", process)

print("\nA process is a running instance of a program.")


# ============================================================
# 13. PROCESS MANAGEMENT
# ============================================================

print("\n13. PROCESS MANAGEMENT")

process_commands = {
    "ps": "Display processes",
    "top": "Monitor running processes",
    "kill": "Send a signal to a process",
    "jobs": "Show shell jobs"
}

for command, purpose in process_commands.items():
    print(command, "->", purpose)


# ============================================================
# 14. ENVIRONMENT VARIABLES
# ============================================================

print("\n14. ENVIRONMENT VARIABLES")

environment_variables = {
    "PATH": "Locations searched for executable commands",
    "HOME": "Current user's home directory",
    "USER": "Current username"
}

for variable, purpose in environment_variables.items():
    print(variable, "->", purpose)


# ============================================================
# 15. STANDARD INPUT AND OUTPUT
# ============================================================

print("\n15. STANDARD INPUT AND OUTPUT")

print("stdin  -> Standard input")
print("stdout -> Standard output")
print("stderr -> Standard error")

print("\nThese streams allow programs and commands")
print("to receive input and produce output.")


# ============================================================
# 16. PIPES
# ============================================================

print("\n16. PIPES")

print("A pipe (|) sends the output of one command")
print("as input to another command.")

print("\nExample:")
print("ls | grep .txt")


# ============================================================
# 17. REDIRECTION
# ============================================================

print("\n17. REDIRECTION")

print(">  -> Redirect output to a file")
print(">> -> Append output to a file")
print("<  -> Use a file as input")

print("\nExample:")
print("echo Hello > message.txt")


# ============================================================
# 18. TEXT PROCESSING
# ============================================================

print("\n18. TEXT PROCESSING COMMANDS")

text_commands = {
    "cat": "Display file contents",
    "less": "Read file content page by page",
    "grep": "Search for matching text",
    "head": "Display beginning of a file",
    "tail": "Display end of a file",
    "wc": "Count lines, words, and characters"
}

for command, purpose in text_commands.items():
    print(command, "->", purpose)


# ============================================================
# 19. PACKAGE MANAGEMENT
# ============================================================

print("\n19. PACKAGE MANAGEMENT")

package_managers = {
    "APT": "Commonly used by Debian-based systems",
    "DNF": "Commonly used by Fedora-based systems",
    "Pacman": "Used by Arch Linux"
}

for manager, purpose in package_managers.items():
    print(manager, "->", purpose)


# ============================================================
# 20. NETWORKING COMMANDS
# ============================================================

print("\n20. BASIC NETWORKING COMMANDS")

network_commands = {
    "ip": "View and manage network configuration",
    "ping": "Test network connectivity",
    "curl": "Transfer data using network protocols",
    "ssh": "Secure remote login",
    "ss": "View network sockets"
}

for command, purpose in network_commands.items():
    print(command, "->", purpose)


# ============================================================
# 21. ARCHIVES AND COMPRESSION
# ============================================================

print("\n21. ARCHIVES AND COMPRESSION")

archive_commands = {
    "tar": "Create and extract archives",
    "gzip": "Compress data",
    "zip": "Create ZIP archives",
    "unzip": "Extract ZIP archives"
}

for command, purpose in archive_commands.items():
    print(command, "->", purpose)


# ============================================================
# 22. LOGS
# ============================================================

print("\n22. SYSTEM LOGS")

print("Linux systems maintain logs that can help")
print("administrators troubleshoot applications,")
print("services, and system activity.")

log_locations = [
    "/var/log",
    "System journal",
    "Application logs"
]

for location in log_locations:
    print("-", location)


# ============================================================
# 23. SHELL SCRIPTING
# ============================================================

print("\n23. SHELL SCRIPTING")

shell_script = """
#!/bin/bash

echo "Hello from Linux"
"""

print(shell_script)

print("Shell scripts can automate repetitive")
print("Linux commands and system tasks.")


# ============================================================
# 24. BASIC LINUX WORKFLOW
# ============================================================

print("\n24. BASIC LINUX WORKFLOW")

print("""
Open Terminal
      ↓
Run Command
      ↓
Read Output
      ↓
Analyze Result
      ↓
Modify Command
      ↓
Automate Repeated Tasks
""")


# ============================================================
# 25. LINUX IN TECHNOLOGY
# ============================================================

print("\n25. LINUX IN TECHNOLOGY")

applications = [
    "Web Servers",
    "Cloud Computing",
    "DevOps",
    "Cybersecurity",
    "Containers",
    "Networking",
    "Software Development",
    "Databases",
    "Embedded Systems"
]

for application in applications:
    print("-", application)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("DAY 01 COMPLETED")
print("=" * 60)

print("""
Today you learned:

1. Linux
2. Linux distributions
3. Terminal and shell
4. Basic Linux commands
5. Linux filesystem
6. Absolute and relative paths
7. File types
8. File permissions
9. Permission structure
10. Users and groups
11. Root user
12. Processes
13. Process management
14. Environment variables
15. Standard input and output
16. Pipes
17. Redirection
18. Text processing
19. Package management
20. Networking commands
21. Archives and compression
22. System logs
23. Shell scripting
24. Basic Linux workflow
25. Linux in technology
""")

