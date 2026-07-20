from __future__ import annotations

from game_of_life.config import load_config
from game_of_life.main import main
from game_of_life.persistence import WorldStore


def test_headless_cli_can_save_and_resume(tmp_path) -> None:
    save_path = tmp_path / "cli-world.db"

    assert main(["--headless", "--no-ai", "--ticks", "10", "--save", str(save_path)]) == 0
    assert (
        main(
            [
                "--headless",
                "--no-ai",
                "--ticks",
                "5",
                "--save",
                str(save_path),
                "--load",
            ]
        )
        == 0
    )

    with WorldStore(save_path) as store:
        events = store.recent_events()
        restored = store.load_latest(load_config(ai_enabled=False))
        mental_ticks = [
            row[0]
            for row in store.connection.execute(
                "SELECT DISTINCT tick FROM mental_states ORDER BY tick"
            )
        ]
    assert save_path.exists()
    assert isinstance(events, list)
    assert restored is not None
    assert restored.state.tick == 15
    assert mental_ticks == [0, 10, 15]
