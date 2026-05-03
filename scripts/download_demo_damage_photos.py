"""Download licensed demo vehicle-damage photos for manual UI testing.

The files come from Wikimedia Commons pages with explicit public-domain or
Creative Commons licensing. Attribution metadata is written alongside the
downloaded originals before selected images are copied into demo claim folders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_ASSETS = ROOT / "demo_assets"
LICENSED_DIR = DEMO_ASSETS / "_licensed_damage_photos"


@dataclass(frozen=True)
class LicensedPhoto:
    key: str
    commons_filename: str
    local_filename: str
    source_url: str
    author: str
    license: str
    license_url: str
    intended_use: str

    @property
    def download_url(self) -> str:
        digest = hashlib.md5(self.commons_filename.encode("utf-8")).hexdigest()
        encoded = urllib.parse.quote(self.commons_filename)
        return f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{encoded}"


PHOTOS = [
    LicensedPhoto(
        key="damaged_car_door",
        commons_filename="Damaged_car_door.jpg",
        local_filename="damaged_car_door_public_domain.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Damaged_car_door.jpg",
        author="Garitzko",
        license="Public domain dedication by copyright holder",
        license_url="https://commons.wikimedia.org/wiki/File:Damaged_car_door.jpg#Licensing",
        intended_use="Minor/moderate side-door damage for approval scenario",
    ),
    LicensedPhoto(
        key="chevrolet_hhr_crash",
        commons_filename="2007_Chevrolet_HHR_involved_in_crash.jpg",
        local_filename="chevrolet_hhr_crash_cc0.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:2007_Chevrolet_HHR_involved_in_crash.jpg",
        author="Crazytales",
        license="Creative Commons CC0 1.0 Universal Public Domain Dedication",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        intended_use="Moderate crash damage for review/fraud scenarios",
    ),
    LicensedPhoto(
        key="fabia_front_right",
        commons_filename="Fabia_I_(2003)_accident_front_right.jpg",
        local_filename="fabia_front_right_cc_by_sa_4.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Fabia_I_(2003)_accident_front_right.jpg",
        author="Hundehalter",
        license="Creative Commons Attribution-ShareAlike 4.0 International",
        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        intended_use="Front-right accident damage for escalation scenario",
    ),
]


CLAIM_PHOTO_MAP = {
    "claim_001_approve": {
        "photo_1.jpg": "damaged_car_door",
        "photo_2.jpg": "chevrolet_hhr_crash",
    },
    "claim_002_escalate": {
        "photo_1.jpg": "fabia_front_right",
        "photo_2.jpg": "chevrolet_hhr_crash",
    },
    "claim_003_fraud_review": {
        "photo_1.jpg": "chevrolet_hhr_crash",
        "photo_2.jpg": "damaged_car_door",
    },
}


def download_file(photo: LicensedPhoto, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        photo.download_url,
        headers={"User-Agent": "ClaimPilot demo asset downloader/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def write_attribution(downloaded: list[LicensedPhoto]) -> None:
    LICENSED_DIR.mkdir(parents=True, exist_ok=True)
    attribution = {
        "purpose": "Licensed vehicle-damage photos for ClaimPilot synthetic demo claims.",
        "sources": [asdict(photo) | {"download_url": photo.download_url} for photo in downloaded],
        "notes": [
            "Public-domain and CC0 images are preferred where available.",
            "CC BY-SA/GFDL images require attribution and compatible sharing for derivatives.",
            "These images are for demo validation only and do not contain real ClaimPilot claimant data.",
        ],
    }
    (LICENSED_DIR / "attribution.json").write_text(
        json.dumps(attribution, indent=2) + "\n",
        encoding="utf-8",
    )


def apply_to_claim_folders(photo_by_key: dict[str, LicensedPhoto]) -> None:
    for claim_folder, mapping in CLAIM_PHOTO_MAP.items():
        claim_path = DEMO_ASSETS / claim_folder
        if not claim_path.exists():
            raise FileNotFoundError(f"Missing demo claim folder: {claim_path}")
        for target_name, photo_key in mapping.items():
            photo = photo_by_key[photo_key]
            source = LICENSED_DIR / photo.local_filename
            target = claim_path / target_name
            shutil.copyfile(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Replace photo_1.jpg/photo_2.jpg in demo claim folders after download.",
    )
    args = parser.parse_args()

    downloaded: list[LicensedPhoto] = []
    for photo in PHOTOS:
        destination = LICENSED_DIR / photo.local_filename
        if destination.exists():
            print(f"using existing {photo.key}: {destination}")
        else:
            download_file(photo, destination)
            print(f"downloaded {photo.key}: {destination}")
        downloaded.append(photo)

    write_attribution(downloaded)
    print(f"wrote attribution: {LICENSED_DIR / 'attribution.json'}")

    if args.apply:
        apply_to_claim_folders({photo.key: photo for photo in downloaded})
        print("updated demo claim photos")


if __name__ == "__main__":
    main()
