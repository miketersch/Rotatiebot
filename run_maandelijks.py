"""
Orkestratie: wordt elke werkdag door de systemd-timer gestart en doet alleen iets op de eerste
handelsdag van de maand (of de eerstvolgende werkdag als een run gemist is).

Stappen: IB Gateway starten (IBC logt in, jij keurt de 2FA-melding goed) -> wachten op de API ->
koersen ophalen -> herbalanceren -> rapport -> gateway stoppen.

Opties:  --forceer   nu draaien ongeacht de datum (test)
         --droog     altijd droogloop, ook als MODUS=echt
"""
import os, sys, subprocess, socket, time, datetime as dt, json
import pandas as pd

HIER = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HIER, "output", "state.json")
PY = sys.executable
MODUS = os.environ.get("MODUS", "droog")          # "droog" of "echt"
PORT = int(os.environ.get("IB_PORT", "4002"))
WACHT_LOGIN_SEC = int(os.environ.get("WACHT_LOGIN_SEC", "1200"))   # 20 min om 2FA goed te keuren

sys.path.insert(0, HIER)
from melding import meld


def eerste_handelsdag_vd_maand(d: dt.date) -> bool:
    # eerste werkdag van de maand (feestdagen op Xetra zijn zeldzaam genoeg; een gemiste run
    # wordt de volgende werkdag ingehaald via de state-file)
    eerste = pd.bdate_range(d.replace(day=1), d.replace(day=1) + pd.Timedelta(days=6))[0].date()
    return d == eerste


def laad_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def bewaar_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"))


def poort_open(poort):
    with socket.socket() as s:
        s.settimeout(2)
        return s.connect_ex(("127.0.0.1", poort)) == 0


def main():
    vandaag = dt.date.today()
    maand = vandaag.strftime("%Y-%m")
    st = laad_state()
    forceer = "--forceer" in sys.argv
    if not forceer:
        if vandaag.weekday() >= 5:
            return
        if st.get("laatste_maand") == maand:
            return
        # draaien op de eerste handelsdag; is die gemist (bot eerder al actief, deze maand nog niet
        # gedraaid) dan de eerstvolgende werkdag inhalen. Allereerste keer: handmatig met --forceer.
        if not eerste_handelsdag_vd_maand(vandaag) and st.get("laatste_maand") is None:
            return

    meld("Rotatiebot start", f"Herbalancering {vandaag}. Keur de IBKR-inlogmelding op je telefoon goed (binnen {WACHT_LOGIN_SEC//60} min).")
    subprocess.run(["sudo", "systemctl", "stop", "sniper-observer"], check=False)   # geheugen vrijmaken voor IB Gateway
    subprocess.run(["sudo", "systemctl", "start", "ibgateway"], check=False)
    t0 = time.time()
    while time.time() - t0 < WACHT_LOGIN_SEC:
        if poort_open(PORT):
            break
        time.sleep(10)
    else:
        meld("Rotatiebot FOUT", "IB Gateway kwam niet online (2FA niet goedgekeurd of inlogprobleem). Morgen nieuwe poging.")
        subprocess.run(["sudo", "systemctl", "stop", "ibgateway"], check=False)
        subprocess.run(["sudo", "systemctl", "start", "sniper-observer"], check=False)
        sys.exit(1)
    time.sleep(20)  # gateway even laten settelen na login

    try:
        subprocess.run([PY, os.path.join(HIER, "data_ophalen.py")], check=True, cwd=HIER)
        args = [PY, os.path.join(HIER, "ibkr_live.py")]
        if MODUS == "echt" and "--droog" not in sys.argv:
            args.append("--echt")
        subprocess.run(args, check=True, cwd=HIER)
        if "--droog" not in sys.argv:          # een droogloop telt niet als de maandelijkse run
            st["laatste_maand"] = maand
            st["laatste_run"] = dt.datetime.now().isoformat(timespec="seconds")
            bewaar_state(st)
    except subprocess.CalledProcessError as e:
        meld("Rotatiebot FOUT", f"Stap mislukt: {e.cmd[-1]} (exit {e.returncode}). Morgen nieuwe poging.")
        sys.exit(1)
    finally:
        subprocess.run(["sudo", "systemctl", "stop", "ibgateway"], check=False)
        subprocess.run(["sudo", "systemctl", "start", "sniper-observer"], check=False)


if __name__ == "__main__":
    main()
