import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI


from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)

from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider


from .config import get_settings

# Configure logger
logger = logging.getLogger(__name__)

def setup_telemetry(app: FastAPI, service_name: str = "ai-agents-api"):
    """
    Configure OpenTelemetry with Azure Monitor exporter
    
    Args:
        app: FastAPI application instance
        service_name: Name of the service for telemetry
    """

    # Limit console logs for OpenTelemetry-related loggers
    logging.getLogger('opentelemetry').setLevel(logging.WARNING)
    logging.getLogger('azure.monitor').setLevel(logging.WARNING)
    logging.getLogger('azure.core').setLevel(logging.WARNING)
    
    # Create a custom console handler with higher threshold for OpenTelemetry
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    logging.getLogger('opentelemetry').addHandler(console_handler)


    settings = get_settings()
    
    # Try to get connection string from settings
    connection_string = getattr(settings, "azure_application_insights_connection_string", None)
    
    if not connection_string:
        logger.warning("Azure Application Insights connection string not found. Telemetry will not be sent to Azure.")
        return

    
    configure_azure_monitor(connection_string=connection_string)
    
    # Set up trace provider with the service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    #trace_provider = TracerProvider(resource=resource)
    
    # Set up Azure Monitor exporter
    azure_exporter = AzureMonitorTraceExporter(
        connection_string=connection_string
    )
    
    # Add exporter to the trace provider
    #trace_provider.add_span_processor(BatchSpanProcessor(azure_exporter))
    
    # Set the trace provider
    #trace.set_tracer_provider(trace_provider)
    
    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    
    logger.info("OpenTelemetry with Azure Monitor exporter has been set up")
    
    return trace.get_tracer(service_name)
