#!/usr/bin/env python3
"""Kiểm tra dependency runtime và tạo thông báo lỗi có thể hành động."""

from __future__ import annotations


class SponsorDependencyError(RuntimeError):
    """Thiếu hoặc lỗi package Sponsor cần cho full builder."""


def sponsor_dependency_message(module_name: str | None = None) -> str:
    missing = f" ({module_name})" if module_name else ""
    return (
        "Thiếu dependency vnstock Sponsor cần cho full builder"
        f"{missing}. Hãy kích hoạt virtualenv của skill, cài/đăng nhập vnstock "
        "Sponsor theo mục 'Cài đặt Sponsor' trong README.md, rồi chạy lại. "
        "Không có fallback community vì pipeline phải fail-closed."
    )


def raise_sponsor_dependency(exc: BaseException) -> None:
    module_name = getattr(exc, "name", None) or type(exc).__name__
    raise SponsorDependencyError(sponsor_dependency_message(module_name)) from None
