"""Serve long-form documentation as Django templates (no markdown engine required)."""

from django.shortcuts import render


def hub(request):
    """Documentation home: links to every topic."""
    return render(request, "documentation/hub.html")


def using_system(request):
    """End-user and operator guide."""
    return render(request, "documentation/using_system.html")


def developer_api(request):
    """REST/JSON integration, amounts, pagination patterns."""
    return render(request, "documentation/developer_api.html")


def smart_contracts(request):
    """TVM model vs EVM, deploy/call lifecycle, opcodes."""
    return render(request, "documentation/smart_contracts.html")


def wallet_architecture(request):
    """Wallet programs vs files, HD/BIP39 concepts, and common wallet topologies."""
    return render(request, "documentation/wallet_architecture.html")


def wallets_security(request):
    """Keys, WIF, operational security, production checklist."""
    return render(request, "documentation/wallets_security.html")


def features_architecture(request):
    """Feature matrix and software architecture for contributors."""
    return render(request, "documentation/features_architecture.html")


def user_guide_payments(request):
    """Payments, mining, and wallet management (step-by-step for users and operators)."""
    return render(request, "documentation/user_guide_payments.html")


def visual_guide(request):
    """Picture-first documentation overview (SVG art; swappable for Figma exports)."""
    return render(request, "documentation/visual_guide.html")
