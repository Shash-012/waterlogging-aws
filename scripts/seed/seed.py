"""A6: load hotspots into DynamoDB and upload replays to S3 for the deployed wlew-core stack.

Usage: python scripts/seed/seed.py [--profile wlew] [--region ap-south-1] [--skip-replays]
Reads table and bucket names from the stack outputs, so nothing is hard-coded.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]


def outputs(session, stack):
    cfn = session.client("cloudformation")
    out = cfn.describe_stacks(StackName=stack)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="wlew")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--stack", default="wlew-core")
    ap.add_argument("--skip-replays", action="store_true")
    args = ap.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    out = outputs(session, args.stack)

    hotspots = json.loads((ROOT / "data" / "hotspots" / "hotspots_contract.json").read_text(encoding="utf-8"))
    cells = json.loads((ROOT / "data" / "hotspots" / "model_cells.json").read_text(encoding="utf-8"))
    table = session.resource("dynamodb").Table(out["HotspotsTableName"])
    with table.batch_writer(overwrite_by_pkeys=["hotspot_id"]) as batch:
        for h in hotspots:
            item = json.loads(json.dumps({**h, "model_cell": cells[h["hotspot_id"]]}), parse_float=Decimal)
            batch.put_item(Item=item)
    print(f"seeded {len(hotspots)} hotspots into {out['HotspotsTableName']}")

    if not args.skip_replays:
        s3 = session.client("s3")
        replay_dir = ROOT / "data" / "replay"
        index = json.loads((replay_dir / "index.json").read_text(encoding="utf-8"))
        for r in index:
            s3.upload_file(str(replay_dir / f"{r['event_id']}.json"), out["ReplayBucketName"],
                           f"replays/{r['event_id']}.json", ExtraArgs={"ContentType": "application/json"})
        s3.upload_file(str(replay_dir / "index.json"), out["ReplayBucketName"], "replays/index.json",
                       ExtraArgs={"ContentType": "application/json"})
        print(f"uploaded {len(index)} replays + index to s3://{out['ReplayBucketName']}/replays/")


if __name__ == "__main__":
    main()
