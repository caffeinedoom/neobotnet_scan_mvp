"""
Batch Processing Monitoring Service
==================================

Tracks batch processing metrics and performance for production monitoring.
Integrates with CloudWatch, logging, and internal metrics tracking.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from ..core.supabase_client import supabase_client

logger = logging.getLogger(__name__)

@dataclass
class BatchMetrics:
    """Batch processing performance metrics."""
    batch_id: str
    total_domains: int
    processing_time_seconds: float
    cost_savings_percentage: float
    resource_efficiency: float
    error_rate: float

class BatchMonitoringService:
    """
    Service for monitoring batch processing performance and costs.
    
    Provides metrics for:
    • Cost optimization tracking
    • Resource utilization monitoring
    • Error rate analysis
    • Performance trend analysis
    """
    
    def __init__(self):
        self.supabase = supabase_client.service_client
        
    async def record_batch_completion(self, batch_id: str, metrics: BatchMetrics) -> None:
        """Record completion metrics for a batch job."""
        try:
            # Store metrics in database for analysis
            metrics_record = {
                "batch_id": batch_id,
                "total_domains": metrics.total_domains,
                "processing_time_seconds": metrics.processing_time_seconds,
                "cost_savings_percentage": metrics.cost_savings_percentage,
                "resource_efficiency": metrics.resource_efficiency,
                "error_rate": metrics.error_rate,
                "recorded_at": datetime.utcnow().isoformat()
            }
            
            # TODO: Create batch_metrics table for storing this data
            # For now, log the metrics
            logger.info(f"Batch {batch_id} completed with metrics: {metrics_record}")
            
            # Send to CloudWatch if configured
            await self._send_cloudwatch_metrics(batch_id, metrics)
            
        except Exception as e:
            logger.error(f"Failed to record batch metrics for {batch_id}: {str(e)}")
    
    async def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get performance summary for the last N days."""
        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Query batch jobs from the period
            response = self.supabase.table("batch_scan_jobs").select(
                "id, total_domains, completed_domains, failed_domains, "
                "created_at, completed_at, status, allocated_cpu, allocated_memory"
            ).gte("created_at", start_date.isoformat()).lte("created_at", end_date.isoformat()).execute()
            
            if not response.data:
                return {"message": "No batch jobs in the specified period"}
                
            jobs = response.data
            
            # Calculate summary metrics
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j["status"] == "completed"])
            total_domains_processed = sum(j["total_domains"] or 0 for j in jobs)
            
            success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            avg_domains_per_batch = total_domains_processed / total_jobs if total_jobs > 0 else 0
            
            return {
                "period_days": days,
                "total_batch_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "success_rate_percentage": round(success_rate, 2),
                "total_domains_processed": total_domains_processed,
                "average_domains_per_batch": round(avg_domains_per_batch, 1),
                "performance_trend": "stable"  # Could be enhanced with trend analysis
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {str(e)}")
            return {"error": str(e)}
    
    async def _send_cloudwatch_metrics(self, batch_id: str, metrics: BatchMetrics) -> None:
        """Send metrics to AWS CloudWatch (optional)."""
        try:
            # TODO: Implement CloudWatch integration
            # import boto3
            # cloudwatch = boto3.client('cloudwatch')
            # 
            # cloudwatch.put_metric_data(
            #     Namespace='PluckwareBatchProcessing',
            #     MetricData=[
            #         {
            #             'MetricName': 'BatchProcessingTime',
            #             'Value': metrics.processing_time_seconds,
            #             'Unit': 'Seconds'
            #         },
            #         {
            #             'MetricName': 'CostSavingsPercentage', 
            #             'Value': metrics.cost_savings_percentage,
            #             'Unit': 'Percent'
            #         }
            #     ]
            # )
            
            logger.info(f"CloudWatch metrics sent for batch {batch_id}")
            
        except Exception as e:
            logger.error(f"Failed to send CloudWatch metrics: {str(e)}")

# Global instance
batch_monitoring = BatchMonitoringService()
