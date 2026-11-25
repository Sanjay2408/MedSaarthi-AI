"""Creates demo accounts for the two-screen demo (patient on a phone, pharmacist on the laptop).

    python scripts/seed_demo.py

LOCAL DEMO ONLY. The passwords below are public because this file is public; they are made-up and
protect nothing. The script refuses to run when MEDSAARTHI_PUBLIC=1, so a hosted server can never
carry these accounts. No real names, emails or prescriptions.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if os.getenv("MEDSAARTHI_PUBLIC") == "1":
    sys.exit("Refusing to create demo accounts on a public server.")

from sqlalchemy import select  # noqa: E402

from api import security  # noqa: E402
from api.db import SessionLocal, init_db  # noqa: E402
from api.models import CONSENT_VERSION, Profile, User, now  # noqa: E402

DEMO_PASSWORD = "demo-only-passphrase"
ACCOUNTS = [
    ("asha.patient@medsaarthi.test", "Asha", "patient", [("Asha", "self", "adult", "hi", False)]),
    ("meera.caregiver@medsaarthi.test", "Meera", "caregiver",
     [("Meera", "self", "adult", "kn", False), ("Arjun (son)", "child", "child", "kn", False),
      ("Ammamma", "parent", "senior", "te", True)]),
    ("ravi.pharmacist@medsaarthi.test", "Ravi (pharmacist)", "pharmacist", [("Ravi", "self", "adult", "en", False)]),
]


def main():
    init_db()
    with SessionLocal() as db:
        for email, name, role, profiles in ACCOUNTS:
            if db.scalar(select(User).where(User.email == email)):
                print("exists ", email)
                continue
            user = User(email=email, name=name, role=role, password_hash=security.hash_password(DEMO_PASSWORD),
                        consent_version=CONSENT_VERSION, consent_at=now())
            for i, (display, relation, age, lang, senior) in enumerate(profiles):
                user.profiles.append(Profile(display_name=display, relation=relation, age_band=age, language=lang,
                                             is_default=(i == 0), large_text=senior, voice_first=senior))
            db.add(user)
            print("created", email, f"({role})")
        db.commit()
    print(f"\nPassword for all three: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
