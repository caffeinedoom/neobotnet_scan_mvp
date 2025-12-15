# NeoBot-Net v2 Module Documentation

**Template-Based Scan Engine Architecture for Asset-Level Reconnaissance**

---

## 📚 Documentation Index

This documentation suite provides comprehensive guidance for understanding, implementing, and extending the NeoBot-Net v2 reconnaissance framework. Written for senior engineers with Go, Docker, and AWS experience.

### Core Documentation

1. **[Architecture Overview](01-ARCHITECTURE-OVERVIEW.md)** *(Est. 15-20 pages)*
   - System design and technical decisions
   - Data model and hierarchy
   - Component interactions and communication patterns
   - Execution modes and scaling architecture
   - Security model and AWS integration

2. **[Module System Deep Dive](02-MODULE-SYSTEM.md)** *(Est. 20-25 pages)*
   - Template-based module architecture
   - Module lifecycle and discovery mechanisms
   - Database-driven configuration patterns
   - Dependency resolution and execution ordering
   - Resource scaling and cost optimization
   - Producer vs Consumer module patterns

3. **[Module Implementation Guide](03-IMPLEMENTING-A-MODULE.md)** *(Est. 30-40 pages)*
   - Step-by-step implementation using real modules (Subfinder, DNSx, HTTPx)
   - Database profile configuration
   - Container implementation patterns
   - Streaming protocol integration
   - Batch mode and database fetch patterns
   - Testing and deployment workflows

4. **[Module Configuration Reference](04-MODULE-CONFIGURATION-REFERENCE.md)** *(Est. 15-20 pages)*
   - Complete `scan_module_profiles` schema documentation
   - Environment variable contract (required/optional)
   - Resource scaling configuration DSL
   - Optimization hints and conventions
   - ECS task definition templates
   - Redis stream naming conventions

5. **[Data Flow & Streaming Protocol](05-DATA-FLOW-AND-STREAMING.md)** *(Est. 15-20 pages)*
   - Request lifecycle from API to ECS execution
   - Redis Streams producer-consumer protocol
   - Database persistence patterns and conflict resolution
   - Module communication and data linkage
   - WebSocket real-time updates
   - Sequence diagrams for common workflows

6. **[Testing & Debugging](06-TESTING-AND-DEBUGGING.md)** *(Est. 15-20 pages)*
   - Local development and testing patterns
   - Integration testing with real infrastructure
   - CloudWatch log analysis and correlation IDs
   - Redis inspection and debugging techniques
   - Performance profiling and optimization
   - Common failure modes and resolutions

---

## 🎯 Quick Navigation by Role

### I want to understand the system
→ Start with **[01-ARCHITECTURE-OVERVIEW.md](01-ARCHITECTURE-OVERVIEW.md)**

### I want to build a new scan module
→ Read **[02-MODULE-SYSTEM.md](02-MODULE-SYSTEM.md)**, then follow **[03-IMPLEMENTING-A-MODULE.md](03-IMPLEMENTING-A-MODULE.md)**

### I need to configure an existing module
→ Reference **[04-MODULE-CONFIGURATION-REFERENCE.md](04-MODULE-CONFIGURATION-REFERENCE.md)**

### I'm debugging a scan failure
→ Jump to **[06-TESTING-AND-DEBUGGING.md](06-TESTING-AND-DEBUGGING.md)**

### I need to understand data flow
→ Study **[05-DATA-FLOW-AND-STREAMING.md](05-DATA-FLOW-AND-STREAMING.md)**

---

## 🏗️ System Overview

NeoBot-Net v2 is a **distributed, template-based reconnaissance framework** designed for bug bounty hunting and asset-level scanning. The architecture is built on:

- **Database-Driven Templates**: Module configuration lives in `scan_module_profiles`, enabling dynamic module addition without code changes
- **Container Isolation**: Each module is a standalone Go container executed on AWS ECS Fargate
- **Streaming Architecture**: Redis Streams enable real-time producer-consumer data flow
- **Intelligent Orchestration**: Automatic dependency resolution, resource allocation, and batch optimization
- **Cost-Optimized**: Dynamic resource scaling based on workload (typical scan: ~$0.01)

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Modules**: Go 1.21+ with ProjectDiscovery SDKs
- **Database**: Supabase (PostgreSQL 15+)
- **Caching/Streaming**: Redis 7.0+ (AWS ElastiCache)
- **Container Orchestration**: AWS ECS Fargate
- **Frontend**: Next.js 14+ with Shadcn UI

---

## 📊 Module Examples

The framework currently implements three production modules:

| Module | Type | Dependencies | Purpose |
|--------|------|--------------|---------|
| **Subfinder** | Producer | None | Subdomain enumeration via passive sources |
| **DNSx** | Consumer | Subfinder | DNS resolution and record enrichment |
| **HTTPx** | Consumer | DNSx | HTTP service probing and fingerprinting |

---

## 🚀 Getting Started

### Prerequisites
- Go 1.21+ and Docker installed locally
- AWS CLI configured with ECS/ECR access
- Supabase project with service role key
- Redis instance (local or ElastiCache)

### Environment Setup
```bash
# Clone repository
cd /root/pluckware/neobotnet/neobotnet_v2

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Testing the Framework
```bash
# Test end-to-end scan
cd docs
export SCAN_TEST_PASSWORD="your-password"
./test_scan.sh --asset-id <your-asset-id>
```

---

## 🔧 Common Workflows

### Adding a New Module
1. Read **[Module System Deep Dive](02-MODULE-SYSTEM.md)** to understand patterns
2. Follow **[Module Implementation Guide](03-IMPLEMENTING-A-MODULE.md)** step-by-step
3. Use **[Configuration Reference](04-MODULE-CONFIGURATION-REFERENCE.md)** for database setup
4. Test with patterns from **[Testing & Debugging](06-TESTING-AND-DEBUGGING.md)**

### Debugging a Scan Failure
1. Check **[Testing & Debugging](06-TESTING-AND-DEBUGGING.md)** for common issues
2. Use correlation ID to query CloudWatch logs
3. Inspect Redis streams with debugging commands
4. Review **[Data Flow](05-DATA-FLOW-AND-STREAMING.md)** to understand expected behavior

### Optimizing Module Performance
1. Review resource scaling in **[Configuration Reference](04-MODULE-CONFIGURATION-REFERENCE.md)**
2. Profile with techniques from **[Testing & Debugging](06-TESTING-AND-DEBUGGING.md)**
3. Understand batching optimizations in **[Module System](02-MODULE-SYSTEM.md)**

---

## 📖 Documentation Conventions

### Code Examples
- All code examples are extracted from production modules (Subfinder, DNSx, HTTPx)
- Template patterns are marked with `// TEMPLATE PATTERN:` comments
- File paths are absolute from repository root

### Diagrams
- **Mermaid.js** for sequence diagrams (GitHub renders natively)
- **ASCII art** for simple component diagrams
- All diagrams are version control friendly

### Terminology
- **Asset**: Top-level entity (e.g., "EpicGames")
- **Apex Domain**: Root domain associated with asset (e.g., "epicgames.com")
- **Subdomain**: Discovered subdomain (e.g., "store.epicgames.com")
- **Module**: Containerized scan tool (e.g., Subfinder, DNSx)
- **Producer**: Module that generates new data (e.g., Subfinder)
- **Consumer**: Module that enriches existing data (e.g., DNSx, HTTPx)
- **Scan Job**: Database record tracking a single module execution
- **Batch**: Grouping of domains for optimized processing

---

## 🔗 External Resources

### Project Infrastructure
- **Infrastructure Docs**: `../infrastructure/README.md`
- **Terraform Configuration**: `../infrastructure/terraform/`
- **AWS ECS Clusters**: Managed via Terraform

### API Documentation
- **Backend API**: `../backend/app/api/v1/`
- **OpenAPI Spec**: Available at `https://aldous-api.neobotnet.com/docs`

### Testing Resources
- **Test Scripts**: `../testing/scripts/`
- **Test Data**: `../testing/data/`
- **API Tests**: `../testing/api/`

---

## 🛠️ Maintenance and Updates

This documentation is maintained alongside the codebase. When making architectural changes:

1. **Update relevant documentation** - Keep docs in sync with code
2. **Add migration notes** - Document breaking changes
3. **Update examples** - Refresh code snippets if patterns change
4. **Version documentation** - Track major architectural versions

### Documentation Version History
- **v1.0** (Nov 2025): Initial comprehensive module documentation
- Template-based architecture established
- Three production modules (Subfinder, DNSx, HTTPx)

---

## 📞 Support

For questions or contributions:
- **GitHub Issues**: Technical problems and feature requests
- **Architecture Questions**: Review these docs first, then open discussion
- **Bug Reports**: Include correlation ID and CloudWatch logs

---

**Last Updated**: November 19, 2025  
**Framework Version**: 2.0  
**Documentation Version**: 1.0  
**Status**: Production Ready ✅
