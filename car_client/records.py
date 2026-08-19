"""Car record normalization and validation shared by the Phase 2 UI."""

CAR_FIELDS = (
    "car_number", "driver_name", "kind_of_car", "type_of_car", "age",
    "nrc_place", "nrc_number", "phone_number", "address", "engine_number",
    "frame_number",
)

VEHICLE_FIELDS = ("car_number", "kind_of_car", "type_of_car", "engine_number", "frame_number")
DRIVER_FIELDS = ("driver_name", "age", "nrc_place", "nrc_number", "phone_number", "address")

REQUIRED_FIELDS = {
    "car_number": "Car Number",
    "driver_name": "Driver Name",
    "nrc_number": "NRC Number",
}

FIELD_DEFINITIONS = (
    ("car_number", "Car Number *", "Example: 1A/1234"),
    ("driver_name", "Driver Name *", "Full name"),
    ("kind_of_car", "Kind of Car", "Example: Saloon"),
    ("type_of_car", "Type of Car", "Example: Toyota Probox"),
    ("age", "Age", "Driver age"),
    ("phone_number", "Phone Number", "09xxxxxxxxx"),
    ("nrc_place", "NRC Place", "Example: 12/LaMaNa"),
    ("nrc_number", "NRC Number *", "NRC number"),
    ("engine_number", "Engine Number", "Engine identifier"),
    ("frame_number", "Frame Number", "Chassis/frame identifier"),
    ("address", "Address", "Driver address"),
)


def validated_record(data: dict) -> dict:
    record = {field: str(data.get(field) or "").strip() for field in CAR_FIELDS}
    missing = [label for field, label in REQUIRED_FIELDS.items() if not record[field]]
    if missing:
        raise ValueError(f"Required fields: {', '.join(missing)}")
    return record


def find_duplicate_records(records: list[dict], candidate: dict, exclude_id=None) -> list[dict]:
    # One vehicle may legitimately be used by several drivers. Engine/frame
    # numbers therefore cannot identify a duplicate record on their own. Warn
    # only when the same vehicle + driver NRC pairing already exists.
    car_number = str(candidate.get("car_number") or "").strip().casefold()
    nrc_number = str(candidate.get("nrc_number") or "").strip().casefold()
    duplicates = []
    for record in records:
        if exclude_id is not None and str(record.get("id")) == str(exclude_id):
            continue
        same_car = str(record.get("car_number") or "").strip().casefold() == car_number
        same_driver = str(record.get("nrc_number") or "").strip().casefold() == nrc_number
        if car_number and nrc_number and same_car and same_driver:
            duplicates.append(record)
    return duplicates
