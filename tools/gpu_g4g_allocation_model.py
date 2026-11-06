#!/usr/bin/env python3
"""Model J81 AGX allocation classes and lifetimes without runtime addresses."""
import json

J81_RESOURCE_REGIONS = (
    {"index": 0, "physical_base": 0x201E00000, "size": 0x2000, "selector": 0x90007},
    {"index": 1, "physical_base": 0x201E10000, "size": 0x1000, "selector": 0x90007},
    {"index": 2, "physical_base": 0x20E100000, "size": 0x2000, "selector": 0x90007},
    {"index": 3, "physical_base": 0x20E104000, "size": 0x1000, "selector": 0x90007},
)
J81_CORE_MMIO = {"physical_base": 0x201000000, "size": 0x20000}

def build_model():
    classes = []
    for index, parameter in enumerate(range(3, 11)):
        classes.append({"class": "firmware-view" if index < 4 else "view-like-auxiliary",
                        "index": index, "size_parameter": parameter,
                        "allocator_flags": "0x22", "map_selector": "0x80007",
                        "registered": index < 4, "address": "unresolved",
                        "lifetime": ["allocate", "map", "address-view", "retain", "release"]})
    for slot, purpose in (("0x27", "host-control"), ("0x29", "host-control"), ("0x4d", "host-control"),
                          ("0x53", "scratch-in"), ("0x54", "scratch-inout")):
        classes.append({"class": purpose, "slot": slot, "registered": False,
                        "address": "unresolved", "lifetime": ["allocate", "map", "address-view", "retain", "release"]})
    return {"execution_allowed": False, "classes": classes,
            "j81_resource_regions": J81_RESOURCE_REGIONS,
            "j81_core_mmio": J81_CORE_MMIO,
            "requirements": ["runtime mapped/backing address pairs", "Linux ownership/cache equivalent",
                              "DART IOVA assignment", "release ordering"]}

if __name__ == "__main__":
    print(json.dumps(build_model(), sort_keys=True))
