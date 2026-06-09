# OPCP AI-Powered Store — Sales Pitch

## Professional Service Labs for OCPC Customers

---

## The Problem

Your customers are building AI workloads. They need GPU compute, but:

- Teams need to deploy Containers, Serverless or AI applications fast, without DevOps overhead
- A single NVIDIA H100 costs **€30k+** — most workloads don't need the full card
- GPU utilization sits at **15-30%** on average across data centers
- Customers want isolated GPU access without managing bare-metal infrastructure


---

## The Solution: OPCP AI-Powered Store for OPCP Core Baremetal Platform

A turnkey platform that lets your OCPC customers **deploy, manage, and share GPU resources** through a single interface — Web, CLI, API, or AI agents.

### One OPCP Platform, Four Access Modes

|        Mode         |                 Use Case                        |
|---------------------|-------------------------------------------------|
| **Web Dashboard**   | Visual management for administrators            |
| **REST API**        | Integration into CI/CD and automation pipelines |
| **CLI**             | DevOps and scripting workflows                  |
| **MCP (AI Agents)** | Autonomous deployment by GenAI agents           |

---

## Key Features: Docker/Podman, Serverless and Shared GPU via Docker on OPCP Baremetal

### NVIDIA MIG — GPU Partitioning Made Simple

With Multi-Instance GPU (MIG), a single NVIDIA H100 becomes **up to 7 isolated GPU slices**, each with dedicated compute, memory, and bandwidth.

```
┌─────────────────────────────────────────────┐
│           NVIDIA H100 (80 GB HBM3)          │
├─────────┬─────────┬─────────┬───────────────┤
│ 1g.10gb │ 1g.10gb │ 2g.20gb │   4g.40gb     │
│ User A  │ User B  │ User C  │   User D      │
│ (Docker)│ (Docker)│ (Docker)│   (Docker)    │
└─────────┴─────────┴─────────┴───────────────┘
```

**What this means for your customers:**

- **Cost reduction**: Split one GPU across multiple workloads — pay for what you use
- **Isolation**: Each Docker container gets its own GPU slice — no interference between tenants
- **Flexibility**: Admins can reconfigure partitions in seconds via the web UI or API
- **No downtime**: Create and destroy GPU instances on-the-fly

### How It Works (3 Clicks)

1. **Enable** shared GPU on a server (toggle switch)
2. **Select** MIG profiles from available partition sizes
3. **Create** isolated GPU instances — ready for Docker workloads

Each instance is accessible via `--gpus` flag in Docker:
```bash
docker run --gpus '"device=MIG-xxx"' my-ai-model:latest
```

---

## Why OVH Professional Services?

### For the Sales Conversation

|                 Customer Pain                |                        OPCP Answer                                         |                      OVH Value                       |
|----------------------------------------------|------------------------------------------------------|-----------------------------------------------|
| "Our AI team can't wait for IT to provision" | Self-service web UI + API for instant GPU access     | Reduced support tickets, faster adoption               |
| "We need AI agents to deploy autonomously"   | MCP protocol + REST API for GenAI automation         | Future-proof positioning in AI infrastructure  |
| "GPUs are too expensive for our team"        | MIG partitioning — share one H100 across 7 workloads | Upsell bare-metal GPU with higher utilization         |
| "We need isolated GPU for each tenant"       | Hardware-level isolation via MIG instances           | Differentiation vs. basic VM-based GPU sharing |
| "We want serverless GPU jobs"                | Serverless Docker execution with GPU passthrough     | New billing model: pay-per-job                     |

### Increase Usage Opportunities

1. **GPU Compute Upsell**: Customers who partition GPUs will consume more GPU hours overall
2. **Professional Services Engagement**: Platform setup, customization, and training
3. **Managed Service Add-on**: OVH operates the platform, customer focuses on AI workloads
4. **Per-Job Billing**: Serverless execution enables consumption-based pricing

---

## Platform Capabilities at a Glance

|        Capability         |                    Description                          |
|---------------------------|---------------------------------------------------------|
| ⚡ **Serverless Docker** | Submit Docker jobs on-demand, GPU-accelerated            |
| 🚀 **App Deployment**    | Clone, build, start, stop, monitor — full lifecycle      |
| 🤖 **AI Agent Support**  | MCP protocol for autonomous GenAI deployment             |
| 🎮 **MIG Shared GPU**    | Partition NVIDIA GPUs into isolated instances per server |
| 🔐 **Multi-tenant Auth** | SSO, 2FA, role-based access, per-user isolation          |
| 🌐 **Multi-server**      | Capacity-based server allocation with replication        |
| 💰 **Billing**           | Activity tracking, cost attribution, usage reports       |
| 🛡️ **Security**          | ModSecurity WAF, OWASP CRS, input validation             |
| 📊 **Monitoring**        | Health checks, real-time logs, database statistics       |

---

## Demo Scenario (15 minutes)

1. **Show the dashboard** — Server list with "Shared-GPU" button
2. **Enable MIG** on a server — Toggle switch, watch MIG mode activate via SSH
3. **List profiles** — Show available partition sizes (1g.10gb, 2g.20gb, 4g.40gb)
4. **Create 3 instances** — Select profiles, click Create, see UUIDs appear
5. **Run a Docker container** on one slice — Prove isolation with `nvidia-smi`
6. **Destroy instances** — One click, clean teardown
7. **Submit a serverless job** — Show the API call, watch it execute in a container

**Key message**: "Your customer goes from bare-metal GPU to isolated, shared, self-service GPU compute in under 60 seconds."

---

## Technical Requirements

- OVH Bare Metal GPU server (NVIDIA H100, A100, or A30 with MIG support)
- Ubuntu 22.04+ with Docker
- Platform auto-installs: NVIDIA drivers, MIG mode, Container Toolkit
- PostgreSQL database (can run on the same server or dedicated instance)

---

## Next Steps

1. **Schedule a live demo** with the customer's technical team
2. **Propose a PoC** on dedicated OVH GPU infrastructure (1-2 weeks)
3. **Size the deployment** based on customer workload profiles
4. **Deliver** as a Professional Services engagement with optional managed operations

---

*OPCP AI-Powered Store — Making GPU compute accessible, shareable, and autonomous.*
