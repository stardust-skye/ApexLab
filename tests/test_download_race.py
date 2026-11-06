import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "download_race", Path(__file__).resolve().parents[1] / "scripts" / "download_race.py"
)
downloader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(downloader)


class DownloadRaceTests(unittest.TestCase):
    def test_inventory_compares_recorded_laps_and_excludes_other_files(self):
        names = list(downloader.REQUIRED) + [
            "VER/1_tel.json", "VER/3_tel.json", "VER/laptimes.json",
            "VER/radio/clip.mp3", "team_radio.json",
        ]
        entries = [{"type": "blob", "path": name, "size": 1, "sha": "a"} for name in names]
        with mock.patch.object(downloader, "tree", return_value=entries), \
             mock.patch.object(downloader, "get_json", return_value={"drv": ["VER", "VER"], "lap": [1, 2]}):
            selected, coverage = downloader.inventory("commit", "Event", "tree")
        self.assertEqual(coverage, [["VER/2_tel.json"], ["VER/3_tel.json"]])
        self.assertEqual(set(selected), set(downloader.REQUIRED) | {"VER/1_tel.json", "VER/3_tel.json"})

    def test_existing_valid_file_is_not_downloaded(self):
        data = b'{"value": 1}'
        entry = {"size": len(data), "sha": downloader.blob_sha(data)}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "VER" / "1_tel.json"
            path.parent.mkdir()
            path.write_bytes(data)
            with mock.patch.object(downloader, "request_bytes", side_effect=AssertionError("network used")):
                record = downloader.download_one("commit", "Event", Path(folder), "VER/1_tel.json",
                                                 entry, {"downloaded_at": "original"})
            self.assertEqual(record["status"], "already_valid")
            self.assertEqual(record["downloaded_at"], "original")

    def test_invalid_file_is_replaced_and_failure_is_explicit(self):
        data = b'{"value": 1}'
        entry = {"size": len(data), "sha": downloader.blob_sha(data)}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x.json"
            path.write_bytes(b"bad")
            with mock.patch.object(downloader, "request_bytes", return_value=data):
                record = downloader.download_one("commit", "Event", Path(folder), "x.json", entry, {})
            self.assertEqual(record["status"], "downloaded")
            self.assertEqual(path.read_bytes(), data)
            with mock.patch.object(downloader, "request_bytes", side_effect=OSError("network down")):
                record = downloader.download_one("commit", "Event", Path(folder), "y.json", entry, {})
            self.assertEqual(record["status"], "failed")
            self.assertIn("network down", record["error"])

    def test_completed_requires_finished_status_and_past_end(self):
        info = {"session_info": {"Type": "Race", "GmtOffset": "-06:00:00",
                                 "StartDate": "2026-01-01T14:00:00", "EndDate": "2026-01-01T16:00:00"},
                "session_status": {"Status": ["Started", "Finished"]}}
        self.assertEqual(downloader.completed_time(info).utcoffset(), dt.timedelta(hours=-6))
        info["session_info"]["GmtOffset"] = "11:00:00"
        self.assertEqual(downloader.completed_time(info).utcoffset(), dt.timedelta(hours=11))
        info["session_status"]["Status"] = ["Started"]
        self.assertIsNone(downloader.completed_time(info))

    def test_rejects_truncated_tree(self):
        with mock.patch.object(downloader, "get_json", return_value={"truncated": True, "tree": []}):
            with self.assertRaisesRegex(RuntimeError, "truncated"):
                downloader.tree("sha", recursive=True)

    def test_incomplete_mexico_falls_back_to_latest_usable_race(self):
        root = [{"type": "tree", "path": "Mexico City Grand Prix", "sha": "mexico"},
                {"type": "tree", "path": "United States Grand Prix", "sha": "usa"}]
        def fake_tree(sha):
            if sha == "commit":
                return root
            return [{"type": "tree", "path": "Race", "sha": sha + "-race"}]
        def fake_json(url):
            if url.endswith("/commits/main"):
                return {"sha": "commit"}
            date = "2026-11-01" if "Mexico" in url else "2026-10-25"
            return {"session_info": {"Type": "Race", "GmtOffset": "-06:00:00",
                                     "StartDate": date + "T14:00:00", "EndDate": date + "T16:00:00"},
                    "session_status": {"Status": ["Finished"]}}
        def fake_inventory(commit, event, sha):
            if event == downloader.MEXICO:
                return {"x": {}}, [["VER/1_tel.json"], []]
            return {"y": {}}, [["BOT/50_tel.json"], []]
        with mock.patch.object(downloader, "tree", side_effect=fake_tree), \
             mock.patch.object(downloader, "get_json", side_effect=fake_json), \
             mock.patch.object(downloader, "inventory", side_effect=fake_inventory):
            commit, event, files, coverage, notes = downloader.discover()
        self.assertEqual((commit, event), ("commit", "United States Grand Prix"))
        self.assertEqual(coverage[0], ["BOT/50_tel.json"])
        self.assertIn("VER/1_tel.json", notes[0])

    def test_checks_json_and_git_blob(self):
        data = b'{"value": 1}'
        entry = {"size": len(data), "sha": downloader.blob_sha(data)}
        downloader.validated(data, entry)
        with self.assertRaises(ValueError):
            downloader.validated(b"not json", entry)
        with self.assertRaisesRegex(ValueError, "invalid JSON constant"):
            downloader.validated(b'{"value": NaN}', entry)
        with self.assertRaises(ValueError):
            downloader.validated(b'{"value": 2}', entry)


if __name__ == "__main__":
    unittest.main()
