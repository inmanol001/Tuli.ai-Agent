import subprocess

from agent.capabilities.tools.browser_tools import browser_search, open_url
from agent.capabilities.tools.macos_tools import open_app
from agent.capabilities.tools.macos_window_tools import (
    NATIVE_TILING_ACTIONS,
    window_native_tiling,
)
from agent.capabilities.tools import macos_observation_tools as obs
from agent.capabilities.tools import macos_space_tools as spaces


class RunRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = []
        self.fail = fail

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if self.fail:
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=command,
                stderr="failed to open",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def test_open_app_normalizes_chrome_and_uses_open_command(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = open_app("chrome")

    assert result.success is True
    assert result.data["app_name"] == "Google Chrome"
    assert recorder.calls[0][0] == ["/usr/bin/open", "-a", "Google Chrome"]
    assert recorder.calls[0][1]["check"] is True
    assert "shell" not in recorder.calls[0][1]


def test_open_app_empty_name_returns_error():
    result = open_app("")

    assert result.success is False
    assert "app_name" in result.error


def test_open_app_subprocess_failure_returns_tool_result(monkeypatch):
    monkeypatch.setattr(subprocess, "run", RunRecorder(fail=True))

    result = open_app("Safari")

    assert result.success is False
    assert result.data["app_name"] == "Safari"
    assert "failed to open" in result.error


def test_open_url_accepts_https_and_uses_default_browser(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = open_url("https://example.com")

    assert result.success is True
    assert result.data["scheme"] == "https"
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://example.com"]
    assert "shell" not in recorder.calls[0][1]


def test_open_url_accepts_http(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = open_url("http://example.com")

    assert result.success is True
    assert result.data["scheme"] == "http"


def test_open_url_normalizes_clear_domain(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = open_url("google.com")

    assert result.success is True
    assert result.data["url"] == "https://google.com"


def test_open_url_blocks_unsafe_schemes_and_local_paths():
    blocked = [
        "",
        "file:///Users/inma/test.txt",
        "javascript:alert(1)",
        "data:text/html,hello",
        "ftp://example.com/file",
        "/Users/inma/test.txt",
    ]

    for url in blocked:
        result = open_url(url)
        assert result.success is False


def test_browser_search_uses_youtube_target(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("omega", target="youtube")

    assert result.success is True
    assert result.data["url"] == "https://www.youtube.com/results?search_query=omega"
    assert result.data["target"] == "youtube"
    assert result.data["opened"] is True
    assert result.metadata["used_helper"] == "open_url"
    assert recorder.calls[0][0] == ["/usr/bin/open", result.data["url"]]


def test_browser_search_auto_resolves_general_web_search(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("informacion sobre macOS Spaces")

    assert result.success is True
    assert result.data["target"] == "web"
    assert "google.com/search" in result.data["url"]


def test_browser_search_auto_opens_known_site_directly(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("github", target="auto")

    assert result.success is True
    assert result.data["target"] == "url"
    assert result.data["url"] == "https://github.com"
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://github.com"]


def test_browser_search_auto_opens_ollama_directly(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("ollama", target="auto")

    assert result.success is True
    assert result.data["target"] == "url"
    assert result.data["url"] == "https://ollama.com"
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://ollama.com"]


def test_browser_search_auto_opens_known_site_domain_directly(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("github.com", target="auto")

    assert result.success is True
    assert result.data["target"] == "url"
    assert result.data["url"] == "https://github.com"
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://github.com"]


def test_browser_search_auto_opens_docs_domain_directly(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("docs.ollama.com", target="auto")

    assert result.success is True
    assert result.data["target"] == "url"
    assert result.data["url"] == "https://docs.ollama.com"
    assert recorder.calls[0][0] == ["/usr/bin/open", "https://docs.ollama.com"]


def test_browser_search_auto_preserves_general_search_for_multiword_query(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("ollama tool calling", target="auto")

    assert result.success is True
    assert result.data["target"] == "web"
    assert "google.com/search" in result.data["url"]


def test_browser_search_opens_direct_url(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("https://youtube.com", target="url")

    assert result.success is True
    assert result.data["target"] == "url"
    assert result.data["url"] == "https://youtube.com"


def test_browser_search_opens_google_home(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("Google", target="google_home")

    assert result.success is True
    assert result.data["url"] == "https://www.google.com"


def test_browser_search_opens_youtube_home(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = browser_search("YouTube", target="youtube_home")

    assert result.success is True
    assert result.data["url"] == "https://www.youtube.com"


def test_browser_search_empty_query_returns_error():
    result = browser_search("")

    assert result.success is False
    assert "query" in result.error


def test_window_native_tiling_rejects_invalid_action():
    result = window_native_tiling("diagonal")

    assert result.success is False
    assert result.data["target"] == "frontmost window"
    assert result.data["details"]["allowed_actions"] == list(NATIVE_TILING_ACTIONS)
    assert "Unsupported native tiling action" in result.error


def test_window_native_tiling_calls_osascript_for_right(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = window_native_tiling("right")

    assert result.success is True
    assert result.data["action"] == "right"
    assert result.data["target"] == "frontmost window"
    assert result.data["method"] == "system_events_window_menu"
    assert result.data["verified"] is False
    assert result.data["menu_path"] == "Window > Move & Resize > Right"
    assert recorder.calls[0][0][0] == "/usr/bin/osascript"
    assert "menu bar item \"Window\"" in recorder.calls[0][0][2]
    assert "menu item \"Right\"" in recorder.calls[0][0][2]


def test_window_native_tiling_handles_permission_error(monkeypatch):
    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            stderr="not authorized",
        )

    monkeypatch.setattr(subprocess, "run", fail)

    result = window_native_tiling("fill")

    assert result.success is False
    assert result.data["action"] == "fill"
    assert result.data["details"]["allowed_actions"] == list(NATIVE_TILING_ACTIONS)
    assert "permission is not available" in result.error.lower()


def test_macos_permissions_check_returns_tool_result(monkeypatch):
    monkeypatch.setattr(obs, "_check_accessibility", lambda: True)
    monkeypatch.setattr(obs, "_check_screen_recording", lambda: False)
    monkeypatch.setattr(obs, "_check_automation", lambda timeout_seconds=5: "unknown")

    result = obs.macos_permissions_check()

    assert result.success is True
    assert result.data == {
        "accessibility": True,
        "screen_recording": False,
        "automation": "unknown",
    }
    assert result.metadata["phase"] == "real_tool"


def test_macos_observe_frontmost_parses_response(monkeypatch):
    monkeypatch.setattr(
        obs,
        "_run_osascript",
        lambda script, timeout_seconds=5: "Google Chrome||com.google.Chrome||YouTube||123",
    )

    result = obs.macos_observe_frontmost()

    assert result.success is True
    assert result.data["app_name"] == "Google Chrome"
    assert result.data["bundle_id"] == "com.google.Chrome"
    assert result.data["window_title"] == "YouTube"
    assert result.data["pid"] == 123


def test_macos_observe_frontmost_handles_permission_error(monkeypatch):
    def fail(script, timeout_seconds=5):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["/usr/bin/osascript"],
            stderr="not authorized",
        )

    monkeypatch.setattr(obs, "_run_osascript", fail)

    result = obs.macos_observe_frontmost()

    assert result.success is False
    assert "not authorized" in result.error


def test_macos_visible_windows_limits_and_sanitizes(monkeypatch):
    windows = [
        {
            "app_name": "Chrome",
            "title": f"Title    {index}",
            "bounds": {"x": 0, "y": 0, "width": 100, "height": 100},
            "window_id": index,
            "layer": 0,
            "onscreen": True,
            "is_frontmost": index == 0,
            "source": "quartz",
        }
        for index in range(25)
    ]
    monkeypatch.setattr(obs, "_quartz_windows", lambda: windows)

    result = obs.macos_visible_windows(max_windows=20)

    assert result.success is True
    assert result.data["count"] == 20
    assert result.data["partial"] is True
    assert result.data["windows"][0]["title"] == "Title    0"


def test_macos_visible_windows_falls_back_and_parses_system_events(monkeypatch):
    monkeypatch.setattr(obs, "_quartz_windows", lambda: [])
    monkeypatch.setattr(
        obs,
        "_run_osascript",
        lambda script, timeout_seconds=5: "Finder||Home   Window||1||2||300||400||true",
    )

    result = obs.macos_visible_windows()

    assert result.success is True
    assert result.data["source"] == "system_events"
    assert result.data["windows"][0]["title"] == "Home Window"


def test_macos_visible_windows_handles_clean_error(monkeypatch):
    monkeypatch.setattr(obs, "_quartz_windows", lambda: [])

    def fail(script, timeout_seconds=5):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["/usr/bin/osascript"],
            stderr="missing permission",
        )

    monkeypatch.setattr(obs, "_run_osascript", fail)
    monkeypatch.setattr(obs, "_check_accessibility", lambda: False)
    monkeypatch.setattr(obs, "_check_screen_recording", lambda: "unknown")

    result = obs.macos_visible_windows()

    assert result.success is False
    assert "missing permission" in result.error
    assert result.data["permissions"]["accessibility"] is False


def test_macos_list_apps_uses_known_apps_aliases_and_installed_apps(monkeypatch):
    monkeypatch.setattr(obs, "_installed_apps_from_dir", lambda path: ["Safari"])

    result = obs.macos_list_apps()

    assert result.success is True
    assert "Safari" in result.data["known_apps"]
    assert result.data["aliases"]["chrome"] == "Google Chrome"
    assert result.data["installed_apps"] == ["Safari"]


def test_macos_space_status_returns_unknown_without_changing_space(monkeypatch):
    monkeypatch.setattr(
        spaces,
        "_read_space_defaults",
        lambda timeout_seconds=5: {
            "current_space": "unknown",
            "current_space_managed_id": None,
            "available_spaces_detected": None,
            "monitors": None,
            "note": spaces.SPACE_STATUS_NOTE,
        },
    )
    monkeypatch.setattr(
        spaces,
        "macos_observe_frontmost",
        lambda timeout_seconds=5: spaces.ToolResult(
            tool_name="macos_observe_frontmost",
            success=True,
            data={"app_name": "Finder"},
        ),
    )
    monkeypatch.setattr(
        spaces,
        "macos_visible_windows",
        lambda timeout_seconds=5: spaces.ToolResult(
            tool_name="macos_visible_windows",
            success=True,
            data={"count": 2},
        ),
    )

    result = spaces.macos_space_status()

    assert result.success is True
    assert result.data["current_space"] == "unknown"
    assert result.data["frontmost_app"] == "Finder"
    assert result.data["visible_windows_count"] == 2
    assert "ManagedSpaceID" in result.data["note"]


def test_macos_space_next_uses_fixed_control_right_script(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = spaces.macos_space_next()

    assert result.success is True
    assert result.data["action"] == "space_next"
    assert result.data["method"] == spaces.SPACE_CONTROL_METHOD
    assert recorder.calls[0][0] == [
        "/usr/bin/osascript",
        "-e",
        'tell application "System Events" to key code 124 using control down',
    ]
    assert "shell" not in recorder.calls[0][1]


def test_macos_space_next_returns_clean_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", RunRecorder(fail=True))

    result = spaces.macos_space_next()

    assert result.success is False
    assert "failed to open" in result.error


def test_macos_space_previous_uses_control_left(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = spaces.macos_space_previous()

    assert result.success is True
    assert "key code 123 using control down" in recorder.calls[0][0][2]


def test_macos_space_mission_control_uses_fixed_script(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = spaces.macos_space_mission_control()

    assert result.success is True
    assert result.data["action"] == "space_mission_control"
    assert "key code 126 using control down" in recorder.calls[0][0][2]


def test_macos_space_switch_desktop_number_validates_range(monkeypatch):
    recorder = RunRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)

    result = spaces.macos_space_switch_desktop_number(2)

    assert result.success is True
    assert result.data["number"] == 2
    assert "key code 19 using control down" in recorder.calls[0][0][2]

    assert spaces.macos_space_switch_desktop_number(0).success is False
    assert spaces.macos_space_switch_desktop_number(10).success is False
    assert spaces.macos_space_switch_desktop_number("2").success is False
