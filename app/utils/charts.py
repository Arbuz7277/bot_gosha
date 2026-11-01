"""Matplotlib charts rendered off the event loop."""
from __future__ import annotations

import asyncio
import io
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402


def _render(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    return buf.getvalue()


def _bar(labels: Sequence[str], values: Sequence[float], title: str, xlabel: str, ylabel: str) -> bytes:
    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()
    ax.bar(list(labels), list(values), width=0.9, alpha=0.8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    return _render(fig)


def _line(values: Sequence[float], title: str, xlabel: str, ylabel: str) -> bytes:
    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()
    ax.plot(range(len(values)), list(values), "b-", linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    return _render(fig)


async def bar_chart(labels, values, title: str, xlabel: str = "", ylabel: str = "") -> bytes:
    return await asyncio.to_thread(_bar, labels, values, title, xlabel, ylabel)


async def line_chart(values, title: str, xlabel: str = "", ylabel: str = "") -> bytes:
    return await asyncio.to_thread(_line, values, title, xlabel, ylabel)
