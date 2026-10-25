"""Exercise the Windows installer in isolated homes, without Python on PATH."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_prompts", ROOT / "scripts/sync-codex-prompts.py")
PROMPTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROMPTS)


class PromptGenerationTest(unittest.TestCase):
    def test_prompt_uses_discovery_not_an_assumed_checkout(self):
        content = PROMPTS.prompt_for(ROOT / "skills/investment-research.md")
        self.assertNotIn("~/ai-berkshire", content)
        self.assertIn("available skills list", content)
        self.assertIn("$ARGUMENTS", content)


@unittest.skipUnless(os.name == "nt", "Windows PowerShell installer")
class CodexInstallTest(unittest.TestCase):
    def setUp(self):
        # Keep every writable test path inside the checkout's ignored tmp directory.
        (ROOT / "tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="codex-install-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "checkout with spaces"
        self.home = self.base / "user home"
        self.codex = self.home / ".codex"
        self.skills = self.home / ".agents/skills"
        (self.repo / "scripts").mkdir(parents=True)
        for name in ("install-codex.ps1", "install-codex-prompts.bat", "install-codex-skills.bat"):
            shutil.copy2(ROOT / "scripts" / name, self.repo / "scripts" / name)
        self.source = self.repo / "codex-skills/investment-research/SKILL.md"
        self.write(self.source, "---\nname: investment-research\ndescription: AI Berkshire research\n---\nNew workflow\n")
        self.write(self.repo / "codex-prompts/investment-research.md",
                   PROMPTS.prompt_for(ROOT / "skills/investment-research.md"))
        self.env = dict(os.environ, USERPROFILE=str(self.home), CODEX_HOME=str(self.codex),
                        CODEX_SKILLS_DIR="", PATH="")
        self.cmd = Path(os.environ["SystemRoot"]) / "System32/cmd.exe"

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def install(self, *args, prompts=True, expected=0):
        script = "install-codex-prompts.bat" if prompts else "install-codex-skills.bat"
        result = subprocess.run([str(self.cmd), "/d", "/c", str(self.repo / "scripts" / script), *args],
                                cwd=self.base, env=self.env, capture_output=True, timeout=60)
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, expected, output)
        return output

    def migrated(self, name="investment-research", root=None):
        path = (root or self.skills) / ("source-command-" + name) / "SKILL.md"
        self.write(path, '---\nname: "source-command-' + name + '"\n'
                   'description: "Run the migrated source command"\n---\nOriginal workflow\n')
        return path

    def test_prompts_install_skills_with_no_python_and_bind_real_path(self):
        self.install()
        installed = self.skills / "investment-research/SKILL.md"
        self.assertEqual(installed.read_bytes(), self.source.read_bytes())
        prompt = self.codex / "prompts/investment-research.md"
        self.assertIn(installed.as_posix(), prompt.read_text(encoding="utf-8"))
        self.assertFalse(prompt.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertFalse((self.codex / "skills").exists())

    def test_skills_only_does_not_install_prompts(self):
        self.install(prompts=False)
        self.assertTrue((self.skills / "investment-research/SKILL.md").is_file())
        self.assertFalse((self.codex / "prompts").exists())

    def test_reinstall_is_idempotent(self):
        self.install()
        self.install()
        self.assertFalse((self.codex / "backups").exists())

    def test_modified_install_is_backed_up_in_full(self):
        old = self.skills / "investment-research/SKILL.md"
        extra = self.skills / "investment-research/references/custom.md"
        self.write(old, "User's previous workflow\n")
        self.write(extra, "Keep this custom resource\n")
        self.write(self.codex / "prompts/investment-research.md", "Old prompt\n")
        self.install()
        backups = list((self.codex / "backups").glob("*/skills/investment-research/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "User's previous workflow\n")
        self.assertEqual((backups[0].parent / "references/custom.md").read_text(), "Keep this custom resource\n")
        self.assertEqual(len(list((self.codex / "backups").glob("*/prompts/investment-research.md"))), 1)

    def test_retirement_is_opt_in_and_preserves_unrelated_skills(self):
        old = self.migrated()
        other = self.migrated("unrelated-command")
        original = old.read_bytes()
        output = self.install()
        self.assertIn("Duplicate workflow retained", output)
        self.assertTrue(old.exists())
        self.install("-RetireMigrated")
        self.assertFalse(old.exists())
        self.assertTrue(other.exists())
        backups = list((self.codex / "backups").glob("*/retired-*/source-command-investment-research/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_unrecognized_same_prefix_is_not_retired(self):
        old = self.skills / "source-command-investment-research/SKILL.md"
        self.write(old, "An unrelated hand-written skill\n")
        self.install("-RetireMigrated")
        self.assertTrue(old.exists())

    def test_migrated_skill_with_custom_description_is_retired(self):
        old = self.skills / "source-command-investment-research/SKILL.md"
        self.write(old, '---\nname: source-command-investment-research\n'
                   'description: A customized description\n---\n'
                   'Use this skill when the user asks to run the migrated source command investment-research.\n')
        self.install("-RetireMigrated")
        self.assertFalse(old.exists())
        self.assertEqual(len(list((self.codex / "backups").glob("*/retired-*/source-command-investment-research/SKILL.md"))), 1)

    def test_legacy_codex_home_copy_is_retired(self):
        old = self.codex / "skills/investment-research/SKILL.md"
        self.write(old, "This skill is generated from skills/investment-research.md for AI Berkshire\n")
        self.install("-RetireMigrated")
        self.assertFalse(old.exists())
        self.assertEqual(len(list((self.codex / "backups").glob("*/retired-*/investment-research/SKILL.md"))), 1)

    def test_custom_locations_and_dollar_in_path(self):
        custom = self.base / "custom $skills"
        self.env["CODEX_SKILLS_DIR"] = str(custom)
        self.env["CODEX_HOME"] = str(self.base / "custom codex")
        self.install()
        installed = custom / "investment-research/SKILL.md"
        self.assertTrue(installed.exists())
        prompt = self.base / "custom codex/prompts/investment-research.md"
        self.assertIn(installed.as_posix().replace("$", "$$"), prompt.read_text(encoding="utf-8"))

    def test_missing_skill_fails_before_any_installation(self):
        self.write(self.repo / "codex-prompts/missing.md", "Missing skill\n")
        output = self.install(expected=1)
        self.assertIn("no matching skill", output)
        self.assertFalse(self.skills.exists())

    def test_source_destination_overlap_is_rejected(self):
        self.env["CODEX_SKILLS_DIR"] = str(self.repo / "codex-skills")
        before = self.source.read_bytes()
        output = self.install(expected=1)
        self.assertIn("overlaps", output)
        self.assertEqual(self.source.read_bytes(), before)

    def test_backup_under_skills_is_rejected(self):
        self.env["CODEX_HOME"] = str(self.skills / "nested-codex")
        output = self.install(expected=1)
        self.assertIn("must not overlap", output)
        self.assertFalse(self.skills.exists())

    def junction(self, link, target):
        link.parent.mkdir(parents=True, exist_ok=True)
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run([str(powershell), "-NoProfile", "-Command",
                                 "New-Item -ItemType Junction -Path '" + str(link) + "' -Target '" + str(target) + "'"],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_linked_target_is_rejected_without_modifying_link_destination(self):
        target = self.base / "linked target"
        self.write(target / "SKILL.md", "Keep original\n")
        self.junction(self.skills / "investment-research", target)
        output = self.install(expected=1)
        self.assertIn("junction", output)
        self.assertEqual((target / "SKILL.md").read_text(), "Keep original\n")

    def test_unrelated_linked_skill_is_left_alone(self):
        target = self.base / "unrelated linked target"
        self.write(target / "SKILL.md", "Unrelated skill\n")
        self.junction(self.skills / "unrelated", target)
        self.install()
        self.assertTrue((self.skills / "unrelated").is_junction())
        self.assertEqual((target / "SKILL.md").read_text(), "Unrelated skill\n")


if __name__ == "__main__":
    unittest.main()
