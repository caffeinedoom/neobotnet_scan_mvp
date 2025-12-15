#!/usr/bin/env python3
"""
Comprehensive Environment Diagnostics for NeoBot-Net v2
Tests environment detection, routing decisions, and capabilities.
"""

import asyncio
import os
import sys
import json
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.environment import (
    EnvironmentDetector,
    EnvironmentRouter,
    OperationType,
    get_current_environment,
    get_environment_capabilities,
    route_operation
)
from app.core.config import settings

class EnvironmentDiagnostics:
    """Comprehensive environment diagnostics and testing."""
    
    def __init__(self):
        self.detector = EnvironmentDetector()
        self.router = EnvironmentRouter()
    
    async def run_full_diagnostics(self) -> Dict[str, Any]:
        """Run complete environment diagnostics."""
        
        print("🚀 NeoBot-Net v2 Environment Diagnostics")
        print("=" * 60)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "environment_detection": {},
            "capabilities_test": {},
            "routing_analysis": {},
            "configuration_audit": {},
            "recommendations": []
        }
        
        # 1. Environment Detection
        print("\n📊 1. Environment Detection")
        print("-" * 30)
        results["environment_detection"] = await self._test_environment_detection()
        
        # 2. Capabilities Testing
        print("\n🔧 2. Capabilities Testing")
        print("-" * 30)
        results["capabilities_test"] = await self._test_capabilities()
        
        # 3. Routing Analysis
        print("\n🎯 3. Routing Analysis")
        print("-" * 30)
        results["routing_analysis"] = await self._test_routing()
        
        # 4. Configuration Audit
        print("\n⚙️  4. Configuration Audit")
        print("-" * 30)
        results["configuration_audit"] = await self._audit_configuration()
        
        # 5. Generate Recommendations
        print("\n💡 5. Recommendations")
        print("-" * 30)
        results["recommendations"] = self._generate_recommendations(results)
        
        # 6. Summary
        print("\n📋 DIAGNOSTIC SUMMARY")
        print("=" * 60)
        await self._print_summary(results)
        
        return results
    
    async def _test_environment_detection(self) -> Dict[str, Any]:
        """Test environment detection capabilities."""
        
        environment = self.detector.detect_environment()
        is_cloud = self.detector._is_cloud_environment()
        is_docker = self.detector._is_docker_environment()
        
        detection_results = {
            "detected_environment": environment,
            "is_cloud_environment": is_cloud,
            "is_docker_environment": is_docker,
            "environment_variables": {
                "ENVIRONMENT": os.getenv('ENVIRONMENT', 'Not Set'),
                "REDIS_HOST": os.getenv('REDIS_HOST', 'Not Set'),
                "ECS_CONTAINER_METADATA_URI": os.getenv('ECS_CONTAINER_METADATA_URI', 'Not Set'),
            },
            "file_system_indicators": {
                "/.dockerenv": os.path.exists('/.dockerenv'),
                "/opt/aws/amazon-ecs-agent": os.path.exists('/opt/aws/amazon-ecs-agent'),
                "/proc/1/cgroup_docker": self._check_cgroup_docker(),
            }
        }
        
        print(f"🌍 Detected Environment: {environment}")
        print(f"☁️  Cloud Environment: {is_cloud}")
        print(f"🐳 Docker Environment: {is_docker}")
        
        return detection_results
    
    def _check_cgroup_docker(self) -> bool:
        """Check if running in Docker via cgroup."""
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except:
            return False
    
    async def _test_capabilities(self) -> Dict[str, Any]:
        """Test all environment capabilities."""
        
        capabilities = await self.detector.get_capabilities()
        
        capability_results = {
            "ecs_access": {
                "available": capabilities.has_ecs,
                "test_result": await self._detailed_ecs_test()
            },
            "local_containers": {
                "available": capabilities.has_local_containers,
                "test_result": await self._detailed_container_test()
            },
            "redis_connectivity": {
                "available": capabilities.has_redis,
                "test_result": await self._detailed_redis_test()
            },
            "database_connectivity": {
                "available": capabilities.has_database,
                "test_result": await self._detailed_database_test()
            },
            "scan_capabilities": {
                "can_scan": capabilities.can_scan,
                "preferred_for_scans": capabilities.preferred_for_scans
            }
        }
        
        # Print results
        for capability, result in capability_results.items():
            if isinstance(result, dict) and 'available' in result:
                status = "✅" if result['available'] else "❌"
                print(f"{status} {capability.replace('_', ' ').title()}: {result['available']}")
        
        return capability_results
    
    async def _detailed_ecs_test(self) -> Dict[str, Any]:
        """Detailed ECS connectivity test."""
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            client = boto3.client('ecs', region_name='us-east-1')
            
            # Test basic connectivity
            clusters = client.list_clusters()
            
            # Test specific cluster access
            cluster_name = f"{settings.project_name}-{settings.environment}-cluster"
            try:
                cluster_desc = client.describe_clusters(clusters=[cluster_name])
                cluster_exists = len(cluster_desc['clusters']) > 0
            except:
                cluster_exists = False
            
            return {
                "boto3_available": True,
                "connectivity": True,
                "cluster_access": True,
                "target_cluster_exists": cluster_exists,
                "target_cluster": cluster_name,
                "total_clusters": len(clusters.get('clusterArns', []))
            }
            
        except (ImportError, NoCredentialsError):
            return {"boto3_available": False, "connectivity": False, "error": "Credentials not available"}
        except ClientError as e:
            return {"boto3_available": True, "connectivity": False, "error": str(e)}
        except Exception as e:
            return {"boto3_available": True, "connectivity": False, "error": str(e)}
    
    async def _detailed_container_test(self) -> Dict[str, Any]:
        """Detailed local container test."""
        try:
            import docker
            client = docker.from_env()
            
            # List all containers
            all_containers = client.containers.list(all=True)
            container_names = [c.name for c in all_containers]
            
            # Check for specific scan containers
            # CLEANUP (2025-10-06): Removed neobotnet-cloud-ssl-analyzer
            scan_containers = {
                'neobotnet-subfinder': 'neobotnet-subfinder' in container_names,
            }
            
            # Check for scan images
            images = client.images.list()
            image_tags = []
            for image in images:
                if image.tags:
                    image_tags.extend(image.tags)
            
            # CLEANUP (2025-10-06): Removed neobotnet-cloud-ssl-analyzer:latest
            scan_images = {
                'neobotnet-subfinder:latest': 'neobotnet-subfinder:latest' in image_tags,
            }
            
            return {
                "docker_available": True,
                "connectivity": True,
                "total_containers": len(all_containers),
                "scan_containers": scan_containers,
                "scan_images": scan_images,
                "container_names": container_names[:10]  # First 10 only
            }
            
        except ImportError:
            return {"docker_available": False, "connectivity": False, "error": "Docker library not installed"}
        except Exception as e:
            return {"docker_available": True, "connectivity": False, "error": str(e)}
    
    async def _detailed_redis_test(self) -> Dict[str, Any]:
        """Detailed Redis connectivity test."""
        try:
            # Use the same test from our Redis health check
            from app.core.config import settings
            import redis.asyncio as redis
            
            redis_config = settings.redis_connection_kwargs
            client = redis.Redis(**redis_config)
            
            # Test basic connectivity
            await client.ping()
            
            # Test read/write operations
            test_key = "diagnostics_test"
            await client.set(test_key, "test_value", ex=10)
            value = await client.get(test_key)
            await client.delete(test_key)
            
            # Get Redis info
            info = await client.info()
            
            await client.aclose()
            
            return {
                "connectivity": True,
                "read_write_test": value == "test_value",
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", "unknown"),
                "host": redis_config["host"],
                "port": redis_config["port"]
            }
            
        except Exception as e:
            return {"connectivity": False, "error": str(e)}
    
    async def _detailed_database_test(self) -> Dict[str, Any]:
        """Detailed database connectivity test."""
        try:
            from app.core.supabase_client import supabase_client
            
            # Test basic connectivity
            result = supabase_client.service_client.table("assets").select("id").limit(1).execute()
            
            # Test table access
            tables_to_test = ["assets", "scan_jobs", "subdomains", "user_quotas"]
            table_access = {}
            
            for table in tables_to_test:
                try:
                    test_result = supabase_client.service_client.table(table).select("*").limit(1).execute()
                    table_access[table] = True
                except Exception as table_error:
                    table_access[table] = False
            
            return {
                "connectivity": True,
                "table_access": table_access,
                "supabase_url": settings.supabase_url[:50] + "..." if len(settings.supabase_url) > 50 else settings.supabase_url
            }
            
        except Exception as e:
            return {"connectivity": False, "error": str(e)}
    
    async def _test_routing(self) -> Dict[str, Any]:
        """Test routing decisions for all operation types."""
        
        routing_results = {}
        
        for operation_type in OperationType:
            try:
                routing_config = await route_operation(operation_type)
                routing_results[operation_type.value] = {
                    "execution_strategy": routing_config["execution_strategy"],
                    "fallback_strategy": routing_config.get("fallback_strategy"),
                    "notifications": routing_config.get("notifications", [])
                }
                
                strategy = routing_config["execution_strategy"]
                fallback = routing_config.get("fallback_strategy", "None")
                print(f"🎯 {operation_type.value}: {strategy} (fallback: {fallback})")
                
            except Exception as e:
                routing_results[operation_type.value] = {"error": str(e)}
                print(f"❌ {operation_type.value}: Error - {str(e)}")
        
        return routing_results
    
    async def _audit_configuration(self) -> Dict[str, Any]:
        """Audit current configuration for consistency."""
        
        config_audit = {
            "environment_variables": {
                "ENVIRONMENT": os.getenv('ENVIRONMENT'),
                "REDIS_HOST": os.getenv('REDIS_HOST'),
                "REDIS_PORT": os.getenv('REDIS_PORT'),
                "DEBUG": os.getenv('DEBUG'),
                "PROJECT_NAME": os.getenv('PROJECT_NAME'),
            },
            "settings_values": {
                "environment": settings.environment,
                "redis_host": settings.redis_host,
                "redis_port": settings.redis_port,
                "debug": settings.debug,
                "project_name": settings.project_name,
                "is_cloud_environment": settings.is_cloud_environment,
            },
            "configuration_issues": []
        }
        
        # Check for configuration issues
        issues = []
        
        # Redis configuration consistency
        if os.getenv('REDIS_HOST') != settings.redis_host:
            issues.append(f"REDIS_HOST mismatch: env={os.getenv('REDIS_HOST')} vs settings={settings.redis_host}")
        
        # Environment consistency
        if os.getenv('ENVIRONMENT') != settings.environment:
            issues.append(f"ENVIRONMENT mismatch: env={os.getenv('ENVIRONMENT')} vs settings={settings.environment}")
        
        # Cloud environment detection consistency
        env_suggests_cloud = settings.environment in ['production', 'staging', 'cloud-dev']
        if env_suggests_cloud != settings.is_cloud_environment:
            issues.append(f"Cloud environment detection inconsistency")
        
        config_audit["configuration_issues"] = issues
        
        print(f"⚙️  Environment: {settings.environment}")
        print(f"🔗 Redis: {settings.redis_host}:{settings.redis_port}")
        print(f"☁️  Cloud Mode: {settings.is_cloud_environment}")
        
        if issues:
            print("⚠️  Configuration Issues:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ Configuration looks consistent")
        
        return config_audit
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on diagnostic results."""
        
        recommendations = []
        capabilities = results["capabilities_test"]
        routing = results["routing_analysis"]
        
        # Scan capability recommendations
        if not capabilities["ecs_access"]["available"] and not capabilities["local_containers"]["available"]:
            recommendations.append(
                "🚨 No scan capabilities detected. Set up local Docker containers for development scanning."
            )
            recommendations.append(
                "💡 Run: docker-compose up --profile testing to start scan containers"
            )
        
        # Redis recommendations
        if not capabilities["redis_connectivity"]["available"]:
            recommendations.append(
                "🚨 Redis not available. Authentication caching and real-time progress will not work."
            )
            recommendations.append(
                "💡 Check Redis connection settings and ensure Redis is running"
            )
        
        # Database recommendations
        if not capabilities["database_connectivity"]["available"]:
            recommendations.append(
                "🚨 Database not available. Core functionality will be impacted."
            )
            recommendations.append(
                "💡 Check Supabase connection settings and credentials"
            )
        
        # Environment-specific recommendations
        environment = results["environment_detection"]["detected_environment"]
        
        if environment == "local-dev":
            if capabilities["ecs_access"]["available"]:
                recommendations.append(
                    "💡 ECS access available in local environment. Scans will use cloud infrastructure."
                )
            else:
                recommendations.append(
                    "💡 Local development mode. Set up AWS credentials for cloud scanning capability."
                )
        
        # Configuration recommendations
        config_issues = results["configuration_audit"]["configuration_issues"]
        if config_issues:
            recommendations.append(
                "⚠️  Configuration inconsistencies detected. Review environment variables."
            )
        
        return recommendations
    
    async def _print_summary(self, results: Dict[str, Any]):
        """Print diagnostic summary."""
        
        capabilities = results["capabilities_test"]
        environment = results["environment_detection"]["detected_environment"]
        
        # Overall health assessment
        critical_capabilities = [
            capabilities["redis_connectivity"]["available"],
            capabilities["database_connectivity"]["available"]
        ]
        
        scan_capabilities = [
            capabilities["ecs_access"]["available"],
            capabilities["local_containers"]["available"]
        ]
        
        if all(critical_capabilities):
            if any(scan_capabilities):
                health_status = "🟢 HEALTHY"
                health_message = "All systems operational with scan capability"
            else:
                health_status = "🟡 DEGRADED"
                health_message = "Core systems operational, no scan capability"
        else:
            health_status = "🔴 CRITICAL"
            health_message = "Critical systems not available"
        
        print(f"Overall Status: {health_status}")
        print(f"Environment: {environment}")
        print(f"Assessment: {health_message}")
        
        # Scan routing summary
        scan_routing = results["routing_analysis"].get("scan_operation", {})
        if scan_routing:
            strategy = scan_routing.get("execution_strategy", "unknown")
            print(f"Scan Strategy: {strategy}")
        
        # Show recommendations
        recommendations = results["recommendations"]
        if recommendations:
            print(f"\n📝 Recommendations ({len(recommendations)}):")
            for rec in recommendations:
                print(f"   {rec}")
        else:
            print("\n✅ No recommendations - system looks good!")

async def main():
    """Main execution function."""
    
    diagnostics = EnvironmentDiagnostics()
    
    try:
        results = await diagnostics.run_full_diagnostics()
        
        # Optionally save results to file
        if len(sys.argv) > 1 and sys.argv[1] == "--save":
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"environment_diagnostics_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            print(f"\n💾 Results saved to: {filename}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
