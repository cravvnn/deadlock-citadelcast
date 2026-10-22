"""Terminal operator desk. Simulation advances only on an explicit step command."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shlex
import sys

from . import __version__
from .presets import Library, defaults, number
from .runtime import CueRunner, MockCamera, SyntheticScene


HELP = """Commands (all cameras/actors/coordinates are SYNTHETIC):
  presets                         List shot bank
  cue ID [SECONDS] [TARGET]        Prepare off-air; TARGET is hero-a or hero-b
  run                             Position mock camera and start cued shot
  step SECONDS                    Advance simulation, 0..30 seconds at 60 Hz
  hold                            Freeze camera only; actors keep moving
  cancel | release                Return to manual; never auto-resume
  status | view                   Show desk status / top-down text preview
  targets                         Show synthetic actor locations
  target ID lose|restore|freeze    Simulate loss, new identity or stale data
  disconnect | reconnect          Simulate camera connection change
  map REVISION                    Simulate a map revision change
  save "FILE.json"                Export shot bank to a NEW file
  load "FILE.json"                Validate and replace bank while released
  help | quit
Nothing advances with wall-clock time. No game connection is available.
"""


class Desk:
    def __init__(self):
        self.library = defaults()
        self.camera = MockCamera()
        self.scene = SyntheticScene()
        self.runner = CueRunner(self.camera, self.scene)
        self.time = 0.0
        self.closed = False

    def status(self):
        r = self.runner
        name = r.preset.name if r.preset else "none"
        target = r.preset.target if r.preset and r.preset.target else "none"
        pose = self.camera.pose
        location = "none" if pose is None else (
            f"({pose.x:.2f}, {pose.y:.2f}, {pose.z:.2f})  "
            f"pitch/yaw/roll=({pose.pitch:.2f}, {pose.yaw:.2f}, {pose.roll:.2f})")
        return (f"Deadlock CitadelCast {__version__} | SYNTHETIC / OFFLINE ONLY\n"
                f"State: {r.state.upper()} | Sim time: {self.time:.3f}s | "
                f"Mock connected: {self.camera.connected} | Camera owned: {self.camera.active}\n"
                f"Map: {self.camera.map_revision}\nShot: {name} | Target: {target}\n"
                f"Shot elapsed: {r.elapsed:.3f}s | Remaining: {max(0, r.duration - r.elapsed):.3f}s\n"
                f"Last camera pose: {location}\n{r.reason}")

    def view(self):
        points = [(p.x, p.y, ".") for p in self.camera.trace]
        if self.runner.preset:
            points.extend((k.x, k.y, "+") for k in self.runner.preset.project.keyframes)
        for id, symbol in (("hero-a", "A"), ("hero-b", "B")):
            target = self.scene.sample(id, self.time)
            if target:
                points.append((*target.position[:2], symbol))
        if self.camera.pose:
            points.append((self.camera.pose.x, self.camera.pose.y, "C"))
        xmin = min((p[0] for p in points), default=-100) - 10
        xmax = max((p[0] for p in points), default=100) + 10
        ymin = min((p[1] for p in points), default=-100) - 10
        ymax = max((p[1] for p in points), default=100) + 10
        grid = [[" " for _ in range(49)] for _ in range(15)]
        for x, y, symbol in points:
            col = round((x - xmin) / (xmax - xmin) * 48)
            row = 14 - round((y - ymin) / (ymax - ymin) * 14)
            grid[row][col] = symbol
        return ("SYNTHETIC top-down preview; auto-scaled, no game geometry/collision\n"
                "+" + "-" * 49 + "+\n" +
                "\n".join("|" + "".join(row) + "|" for row in grid) +
                "\n+" + "-" * 49 + "+\nC last camera | A/B actors | . trace | + keys\n"
                "Follow keys are world-axis offsets, not world positions.")

    def execute(self, command):
        if self.closed:
            raise ValueError("Desk is closed")
        # Keep Windows backslashes literal, allow quoted paths with spaces.
        words = [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w
                 for w in shlex.split(command, posix=False)]
        if not words or words[0].startswith("#"):
            return ""
        op, *args = words
        counts = {"presets": (0,), "cue": (1, 2, 3), "run": (0,), "step": (1,),
                  "hold": (0,), "cancel": (0,), "release": (0,), "status": (0,),
                  "view": (0,), "targets": (0,), "target": (2,), "disconnect": (0,),
                  "reconnect": (0,), "map": (1,), "save": (1,), "load": (1,),
                  "help": (0,), "quit": (0,)}
        if op not in counts or len(args) not in counts[op]:
            raise ValueError("Unknown command or wrong arguments; enter help")
        if op == "help":
            return HELP
        if op == "presets":
            return "\n".join(f"{p.id:12} {p.project.duration:5.1f}s {p.mode:8} {p.name}"
                             for p in self.library)
        if op == "status":
            self.runner.update(self.time)
            return self.status()
        if op == "view":
            return self.view()
        if op == "targets":
            return "\n".join(f"SYNTHETIC {id}: {self.scene.sample(id, self.time)}"
                             for id in self.scene.generations)
        if op == "cue":
            preset = self.library.get(args[0])
            if len(args) == 3:
                preset.target = args[2]
            duration = float(args[1]) if len(args) >= 2 else None
            self.runner.cue(preset, self.time, duration)
        elif op == "run":
            self.runner.run(self.time)
        elif op == "step":
            seconds = number(float(args[0]), "step", 0, 30)
            end = number(self.time + seconds, "simulation time", 0, 1_000_000)
            count = max(1, math.ceil(seconds * 60))
            start = self.time
            for i in range(1, count + 1):
                self.time = end if i == count else start + seconds * i / count
                self.runner.update(self.time)
        elif op == "hold":
            self.runner.hold(self.time)
        elif op in ("cancel", "release", "quit"):
            self.runner.release()
            self.closed = op == "quit"
        elif op == "target":
            self.scene.change(args[0], args[1], self.time)
            self.runner.update(self.time)
        elif op in ("disconnect", "reconnect"):
            self.camera.connect(op == "reconnect")
            self.runner.update(self.time)
        elif op == "map":
            self.camera.set_map(args[0])
            self.runner.update(self.time)
        elif op == "save":
            self.library.save(args[0])
            return "Synthetic library saved: " + args[0]
        elif op == "load":
            if self.runner.state not in ("manual", "fault"):
                raise ValueError("Release before replacing the preset library")
            library = Library.load(args[0])
            self.runner.release()
            self.library = library
            return "Synthetic library loaded: " + args[0]
        return self.status()


def main(argv=None, stdin=None, stdout=None):
    parser = argparse.ArgumentParser(description="Deadlock CitadelCast — synthetic offline terminal desk")
    parser.add_argument("--demo", action="store_true", help="print a deterministic simulation and exit")
    parser.add_argument("--script", type=Path, help="read desk commands from a UTF-8 file; no shell execution")
    options = parser.parse_args(argv)
    if options.demo and options.script:
        parser.error("Choose --demo or --script")
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    desk = Desk()
    script_stream = None
    errors = 0
    try:
        if options.demo:
            commands = iter(("presets", "cue walker 6", "run", "step 3", "view", "release",
                             "cue hero-follow 8 hero-b", "run", "step 2", "hold", "step 1",
                             "view", "release", "quit"))
        elif options.script:
            script_stream = options.script.open(encoding="utf-8")
            commands = iter(script_stream)
        else:
            commands = iter(stdin)
        interactive = not options.demo and not options.script and stdin.isatty()
        print(desk.status(), file=stdout)
        print("Enter help for controls. Simulation moves only with step.", file=stdout)
        while not desk.closed:
            if interactive:
                print("offline> ", end="", file=stdout, flush=True)
            command = next(commands, None)
            if command is None:
                break
            try:
                output = desk.execute(command.strip())
                if output:
                    print(output, file=stdout)
                if desk.runner.state == "fault" and not interactive:
                    errors += 1
                    break
            except (ValueError, OSError) as error:
                print("Error: " + str(error), file=stdout)
                errors += 1
                if not interactive:
                    break
    except (OSError, UnicodeError) as error:
        print("Error: " + str(error), file=stdout)
        errors += 1
    except KeyboardInterrupt:
        print("Interrupted; mock camera released.", file=stdout)
    finally:
        desk.runner.release()
        if script_stream:
            script_stream.close()
    return 1 if errors else 0
