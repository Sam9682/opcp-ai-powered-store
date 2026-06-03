# List of Available Applications 📋

This document provides a summary of the default applications available on the OPCP AiPoweredStore Docker AI platform.

These applications are defined in `conf/default_apps` and are automatically provisioned for users.

---

## Applications

### 1. ai-staticwebsite 🌐
- **Description**: Simple static Web Site
- **Repository**: [github.com/Sam9682/ai-staticwebsite](https://github.com/Sam9682/ai-staticwebsite.git)
- **Repository Size**: ~4 MB
- **Docker Build Time**: ~29s | Start: ~29s | Stop: ~10s

---

### 2. ai-shai-web-interface 🖥️
- **Description**: Interface Web pour Shai
- **Repository**: [github.com/Sam9682/ai-hypervisia](https://github.com/Sam9682/ai-hypervisia.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

### 3. opcp-openstack-first-steps �
- **Description**: OPCP Openstack First Steps
- **Repository**: [github.com/Sam9682/opcp-openstack-first-steps](https://github.com/Sam9682/opcp-openstack-first-steps.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

### 4. opcp-openstack-automation ⚙️
- **Description**: OPCP Openstack Automation
- **Repository**: [github.com/Sam9682/opcp-openstack-automation](https://github.com/Sam9682/opcp-openstack-automation.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

### 5. opcp-psmc-dashboard �
- **Description**: OPCP PSMC Dashboard
- **Repository**: [github.com/Sam9682/opcp-psmc-dashboard](https://github.com/Sam9682/opcp-psmc-dashboard.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

### 6. opcp-openstack-simulator 🧪
- **Description**: OPCP Openstack Simulator
- **Repository**: [github.com/Sam9682/opcp-openstack-simulator](https://github.com/Sam9682/opcp-openstack-simulator.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

### 7. opcp-introduction �
- **Description**: OPCP Introduction - non tech
- **Repository**: [github.com/Sam9682/opcp-introduction](https://github.com/Sam9682/opcp-introduction.git)
- **Repository Size**: ~10 MB
- **Docker Build Time**: ~30s | Start: ~30s | Stop: ~10s

---

## Configuration Format

Applications are defined in `conf/default_apps` with the following format:

```
name | description | git_url | git_repo_size (MB) | docker_build_duration (s) | docker_start_duration (s) | docker_stop_duration (s) | docker_ps_duration (s)
```

## How It Works

1. When the platform starts, applications listed in `conf/default_apps` are loaded into the database
2. The admin user is automatically assigned all default applications
3. New users can be assigned applications by the administrator from the Users management panel
4. Each application is cloned from its Git repository, built with Docker, and deployed with its own isolated ports
