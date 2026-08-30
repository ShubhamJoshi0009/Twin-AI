"""Sample supply chain datasets for demos and testing."""

from __future__ import annotations

from typing import Any, Dict, List

SAMPLE_SUPPLIERS: List[Dict[str, Any]] = [
    {
        "name": "GlobalTech Components",
        "contact_name": "John Chen",
        "email": "john@globaltech.com",
        "location": "Shenzhen, China",
        "country": "China",
        "product_categories": ["electronics", "components"],
        "lead_time_days": 14,
        "cost_per_unit": 25.0,
        "capacity": 5000,
        "quality_rating": 4.5,
        "contract_expiry": "2027-12-31",
    },
    {
        "name": "EuroParts Manufacturing",
        "contact_name": "Maria Schmidt",
        "email": "maria@europarts.de",
        "location": "Munich, Germany",
        "country": "Germany",
        "product_categories": ["mechanical", "precision"],
        "lead_time_days": 7,
        "cost_per_unit": 45.0,
        "capacity": 2000,
        "quality_rating": 4.8,
        "contract_expiry": "2026-06-30",
    },
    {
        "name": "QuickShip Logistics",
        "contact_name": "Sarah Johnson",
        "email": "sarah@quickship.com",
        "location": "Los Angeles, USA",
        "country": "USA",
        "product_categories": ["logistics", "packaging"],
        "lead_time_days": 3,
        "cost_per_unit": 10.0,
        "capacity": 10000,
        "quality_rating": 4.2,
        "contract_expiry": "2025-12-31",
    },
    {
        "name": "AsiaRaw Materials",
        "contact_name": "Wei Liu",
        "email": "wei@asiaraw.com",
        "location": "Guangzhou, China",
        "country": "China",
        "product_categories": ["raw_materials", "metals"],
        "lead_time_days": 21,
        "cost_per_unit": 15.0,
        "capacity": 8000,
        "quality_rating": 3.8,
        "contract_expiry": "2026-09-30",
    },
    {
        "name": "Prime Supply Co",
        "contact_name": "David Miller",
        "email": "david@primesupply.com",
        "location": "Chicago, USA",
        "country": "USA",
        "product_categories": ["general", "components"],
        "lead_time_days": 5,
        "cost_per_unit": 30.0,
        "capacity": 3000,
        "quality_rating": 4.3,
        "contract_expiry": "2027-03-31",
    },
]

SAMPLE_WAREHOUSES: List[Dict[str, Any]] = [
    {
        "name": "East Coast Distribution Center",
        "location": "Newark, NJ",
        "capacity": 50000,
        "storage_cost_per_unit": 0.50,
        "manager": "Mike Thompson",
    },
    {
        "name": "West Coast Hub",
        "location": "Los Angeles, CA",
        "capacity": 35000,
        "storage_cost_per_unit": 0.65,
        "manager": "Lisa Park",
    },
    {
        "name": "Central Warehouse",
        "location": "Dallas, TX",
        "capacity": 40000,
        "storage_cost_per_unit": 0.45,
        "manager": "James Wilson",
    },
]

SAMPLE_INVENTORY: List[Dict[str, Any]] = [
    {
        "product_name": "Smart Widget Pro",
        "product_sku": "SWP-001",
        "category": "electronics",
        "current_stock": 2500,
        "reorder_level": 500,
        "safety_stock": 200,
        "max_stock": 5000,
        "unit_cost": 45.0,
        "turnover_rate": 3.2,
    },
    {
        "product_name": "Precision Gear Assembly",
        "product_sku": "PGA-002",
        "category": "mechanical",
        "current_stock": 800,
        "reorder_level": 300,
        "safety_stock": 150,
        "max_stock": 2000,
        "unit_cost": 120.0,
        "turnover_rate": 1.8,
    },
    {
        "product_name": "Basic Connector Kit",
        "product_sku": "BCK-003",
        "category": "components",
        "current_stock": 150,
        "reorder_level": 200,
        "safety_stock": 100,
        "max_stock": 3000,
        "unit_cost": 8.0,
        "turnover_rate": 4.5,
    },
    {
        "product_name": "Premium Housing Unit",
        "product_sku": "PHU-004",
        "category": "mechanical",
        "current_stock": 4500,
        "reorder_level": 500,
        "safety_stock": 250,
        "max_stock": 3000,
        "unit_cost": 85.0,
        "turnover_rate": 0.3,
    },
    {
        "product_name": "Control Board X1",
        "product_sku": "CBX-005",
        "category": "electronics",
        "current_stock": 0,
        "reorder_level": 100,
        "safety_stock": 50,
        "max_stock": 1500,
        "unit_cost": 200.0,
        "turnover_rate": 2.1,
    },
]

SAMPLE_SHIPMENTS: List[Dict[str, Any]] = [
    {
        "shipment_number": "SHP-2024-001",
        "product_name": "Smart Widget Pro",
        "quantity": 1000,
        "origin": "Shenzhen, China",
        "destination": "Newark, NJ",
        "distance_km": 12000,
        "fuel_cost": 2500.0,
        "transport_cost": 8500.0,
        "status": "in_transit",
    },
    {
        "shipment_number": "SHP-2024-002",
        "product_name": "Precision Gear Assembly",
        "quantity": 500,
        "origin": "Munich, Germany",
        "destination": "Dallas, TX",
        "distance_km": 8500,
        "fuel_cost": 1800.0,
        "transport_cost": 6200.0,
        "status": "delivered",
    },
    {
        "shipment_number": "SHP-2024-003",
        "product_name": "Basic Connector Kit",
        "quantity": 5000,
        "origin": "Los Angeles, CA",
        "destination": "Newark, NJ",
        "distance_km": 4500,
        "fuel_cost": 900.0,
        "transport_cost": 3200.0,
        "status": "delayed",
    },
    {
        "shipment_number": "SHP-2024-004",
        "product_name": "Control Board X1",
        "quantity": 200,
        "origin": "Guangzhou, China",
        "destination": "Los Angeles, CA",
        "distance_km": 11000,
        "fuel_cost": 2200.0,
        "transport_cost": 7800.0,
        "status": "pending",
    },
]


def get_sample_suppliers() -> List[Dict[str, Any]]:
    return SAMPLE_SUPPLIERS.copy()


def get_sample_warehouses() -> List[Dict[str, Any]]:
    return SAMPLE_WAREHOUSES.copy()


def get_sample_inventory() -> List[Dict[str, Any]]:
    return SAMPLE_INVENTORY.copy()


def get_sample_shipments() -> List[Dict[str, Any]]:
    return SAMPLE_SHIPMENTS.copy()
