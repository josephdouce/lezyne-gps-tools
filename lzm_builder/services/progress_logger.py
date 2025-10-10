"""
Progress Logger Service

A clean way to handle verbose output without cluttering core business logic.
Uses decorator pattern to wrap methods with progress reporting.
"""

import time
from typing import Any, Callable, Optional
from functools import wraps


class ProgressLogger:
    """
    Handles all progress reporting and statistics display.
    Keeps verbose output separate from core business logic.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.start_times = {}
        
    def phase(self, phase_name: str) -> 'PhaseContext':
        """Context manager for tracking phases with timing."""
        return PhaseContext(self, phase_name)
    
    def log(self, message: str, emoji: str = "📊"):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"{emoji} {message}")
    
    def log_stats(self, stats: dict, prefix: str = ""):
        """Log statistics in a formatted way."""
        if not self.verbose:
            return
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                if isinstance(value, int) and value > 1000:
                    formatted_value = f"{value:,}"
                elif isinstance(value, float):
                    formatted_value = f"{value:.1f}"
                else:
                    formatted_value = str(value)
            else:
                formatted_value = str(value)
            self.log(f"{prefix}{key}: {formatted_value}")


class PhaseContext:
    """Context manager for timing and reporting phases."""
    
    def __init__(self, logger: ProgressLogger, phase_name: str):
        self.logger = logger
        self.phase_name = phase_name
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log(f"{self.phase_name}...", "⏱️")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        self.logger.log(f"{self.phase_name} complete ({elapsed:.1f}s)", "✅")


def progress_tracked(phase_name: str):
    """Decorator to automatically track progress for methods."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if hasattr(self, '_logger') and self._logger.verbose:
                with self._logger.phase(phase_name):
                    return func(self, *args, **kwargs)
            else:
                return func(self, *args, **kwargs)
        return wrapper
    return decorator


class PeriodicReporter:
    """Helper for reporting progress at regular intervals."""
    
    def __init__(self, logger: ProgressLogger, interval: int, message_template: str):
        self.logger = logger
        self.interval = interval
        self.message_template = message_template
        self.last_report_time = time.time()
        self.count = 0
        
    def increment(self, **kwargs):
        """Increment counter and report if interval reached."""
        self.count += 1
        if self.count % self.interval == 0:
            current_time = time.time()
            elapsed = current_time - self.last_report_time
            rate = self.interval / elapsed if elapsed > 0 else 0
            
            message_kwargs = {
                'count': self.count,
                'rate': rate,
                **kwargs
            }
            message = self.message_template.format(**message_kwargs)
            self.logger.log(message)
            self.last_report_time = current_time