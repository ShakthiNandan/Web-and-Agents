"""Adapter registry for discovering, configuring, and dispatching to agent providers."""
import os
from typing import Dict, List, Optional
from .base import BaseAdapter, ExecutionResult, ProviderInfo
from .antigravity import AntigravityAdapter
from .opencode import OpenCodeAdapter
from .claude import ClaudeCodeAdapter
from .codex import CodexAdapter
from .cline import ClineAdapter


class AdapterRegistry:
    """Registry maintaining all supported agent adapters."""

    def __init__(self):
        self._adapters: Dict[str, BaseAdapter] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register the built-in adapters."""
        for adapter in [
            AntigravityAdapter(),
            OpenCodeAdapter(),
            ClaudeCodeAdapter(),
            CodexAdapter(),
            ClineAdapter(),
        ]:
            self.register(adapter)

    def register(self, adapter: BaseAdapter) -> None:
        """Register an agent adapter."""
        self._adapters[adapter.id.lower()] = adapter

    def unregister(self, provider_id: str) -> Optional[BaseAdapter]:
        """Unregister an adapter by ID."""
        return self._adapters.pop(provider_id.lower(), None)

    def get(self, provider_id: Optional[str]) -> Optional[BaseAdapter]:
        """Look up an adapter by provider ID (case-insensitive)."""
        if not provider_id:
            return None
        return self._adapters.get(str(provider_id).strip().lower())

    def get_default_provider(self) -> BaseAdapter:
        """Resolve the default provider based on configuration and availability."""
        env_def = os.environ.get("AGENT_HUB_DEFAULT_PROVIDER")
        if env_def and self.get(env_def):
            return self.get(env_def)

        # Default to Antigravity if present
        agy = self.get("agy")
        if agy and agy.is_available():
            return agy

        # Look for any available provider
        for ad in self._adapters.values():
            if ad.is_available():
                return ad

        # Fall back to agy or first registered
        return agy or next(iter(self._adapters.values()))

    def list_providers(self) -> List[ProviderInfo]:
        """List provider information for all registered adapters."""
        return [adapter.get_provider_info() for adapter in self._adapters.values()]

    def list_available_providers(self) -> List[ProviderInfo]:
        """List provider information only for currently installed/runnable adapters."""
        return [adapter.get_provider_info() for adapter in self._adapters.values() if adapter.is_available()]

    def run_task(
        self,
        provider_id: Optional[str],
        prompt: str,
        workspace: Optional[str] = None,
        timeout: int = 60,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Dispatch a synchronous task run to the specified or default provider."""
        adapter = self.get(provider_id) if provider_id else self.get_default_provider()
        if not adapter:
            return ExecutionResult(
                status="error",
                provider=str(provider_id or "unknown"),
                error=f"Unknown agent provider '{provider_id}'. Available providers: {list(self._adapters.keys())}",
                returncode=-1,
            )
        return adapter.run_task(
            prompt=prompt,
            workspace=workspace,
            timeout=timeout,
            model=model,
            auto_approve=auto_approve,
            extra_flags=extra_flags,
        )

    def launch_background(
        self,
        provider_id: Optional[str],
        prompt: str,
        workspace: Optional[str] = None,
        model: Optional[str] = None,
        auto_approve: bool = True,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Dispatch a background task launch to the specified or default provider."""
        adapter = self.get(provider_id) if provider_id else self.get_default_provider()
        if not adapter:
            return ExecutionResult(
                status="error",
                provider=str(provider_id or "unknown"),
                error=f"Unknown agent provider '{provider_id}'. Available providers: {list(self._adapters.keys())}",
                returncode=-1,
            )
        return adapter.launch_background(
            prompt=prompt,
            workspace=workspace,
            model=model,
            auto_approve=auto_approve,
            extra_flags=extra_flags,
        )

    def open_terminal(
        self,
        provider_id: Optional[str],
        workspace: Optional[str] = None,
        prompt: Optional[str] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> ExecutionResult:
        """Dispatch an interactive terminal session to the specified or default provider."""
        adapter = self.get(provider_id) if provider_id else self.get_default_provider()
        if not adapter:
            return ExecutionResult(
                status="error",
                provider=str(provider_id or "unknown"),
                error=f"Unknown agent provider '{provider_id}'. Available providers: {list(self._adapters.keys())}",
                returncode=-1,
            )
        return adapter.open_terminal(
            workspace=workspace,
            prompt=prompt,
            extra_flags=extra_flags,
        )


_GLOBAL_REGISTRY: Optional[AdapterRegistry] = None


def get_registry(reset: bool = False) -> AdapterRegistry:
    """Return the global AdapterRegistry singleton."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None or reset:
        _GLOBAL_REGISTRY = AdapterRegistry()
    return _GLOBAL_REGISTRY
