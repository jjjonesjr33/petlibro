from typing import Dict, Type
from .device import Device
from .feeders import Feeder
from .feeders.granary_feeder import GranaryFeeder
from .feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain  # Import the new class

product_name_map : Dict[str, Type[Device]] = {
    "Granary Feeder": GranaryFeeder,
    "One RFID Smart Feeder": OneRFIDSmartFeeder,
    "Dockstream Smart RFID Fountain": DockstreamSmartRFIDFountain  # Add the new product
}
