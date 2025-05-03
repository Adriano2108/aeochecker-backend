"""
Base analyzer class for website analysis.
This module contains the base analyzer class that all specialized analyzers inherit from.
"""

from typing import Dict, Any, Tuple
from abc import ABC, abstractmethod

class BaseAnalyzer(ABC):
    """Base class for all website analyzers."""
    
    @abstractmethod
    async def analyze(self, url: str) -> Tuple[float, str]:
        """
        Analyze a website and return a score and explanation.
        
        Args:
            url: The URL of the website to analyze.
            
        Returns:
            A tuple containing:
            - float: The score (0-100) representing the analysis result
            - str: A textual explanation or details of the analysis
        """
        pass 