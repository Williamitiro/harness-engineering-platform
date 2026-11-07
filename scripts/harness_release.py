#!/usr/bin/env python3
"""Instala o Harness no computador a partir de uma versão marcada (tag), fora da pasta de desenvolvimento.

Problema que resolve: a `setup-harness` grava o caminho do `harnessctl` de quem a instalou. Se esse caminho é a pasta
onde se desenvolve o Harness (`C:\\dev\\harness-engineering`), trocar de branch ali muda, ou quebra, o que está
instalado. O padrão (pipx/uv tool, Homebrew, plugins versionados) é instalar uma versão fixa numa pasta própria:

  ~/.harness-engineering/<tag>/   cópia exata da tag, sem .git, nunca editada (RELEASE.json diz tag e commit)
  ~/.harness-engineering/current  atalho para a versão em uso (é o caminho que se usa nos comandos)

Fluxo (`install --tag vX --apply`): extrai a tag (git archive) numa pasta nova; remove o pacote do computador com o
harnessctl que o instalou antes; instala e confere com o harnessctl da versão nova; só então aponta `current`.
Se a instalação nova falhar, reinstala a anterior. Sem `--apply`, só mostra o plano e não grava nada.

Uso:
  python scripts/harness_release.py install --tag v1.0.0            # plano
  python scripts/harness_release.py install --tag v1.0.0 --apply    # instala
  python scripts/harness_release.py status
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCATION = Path(".agents/skills/setup-harness/harness-location.json")


class ReleaseError(RuntimeError):
    pass


def git(repo: Path, *args: str, binary: bool = False) -> str | bytes:
    proc = subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false", *args],
                          capture_output=True, check=False, timeout=120)
    if proc.returncode != 0:
        raise ReleaseError(f"git {args[0]} falhou: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return proc.stdout if binary else proc.stdout.decode("utf-8").strip()


def harnessctl(path: Path, *args: str, home: Path) -> dict:
    proc = subprocess.run([sys.executable, str(path), *args, "--home", str(home)],
                          capture_output=True, encoding="utf-8", errors="replace", check=False, timeout=300)
    if proc.returncode != 0:
        try:
            reason = json.loads(proc.stderr).get("reason")
        except ValueError:
            reason = proc.stderr.strip()[:300]
        raise ReleaseError(f"{Path(path).parents[1].name}: {' '.join(args)} → {reason}")
    return json.loads(proc.stdout)


def tag_commit(repo: Path, tag: str) -> str:
    try:
        git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}")
    except ReleaseError:
        raise ReleaseError(f"'{tag}' não é uma tag deste repositório; instale só versões marcadas") from None
    return str(git(repo, "rev-parse", f"{tag}^{{commit}}"))


def export(repo: Path, tag: str, commit: str, target: Path) -> None:
    """Extrai a tag numa pasta temporária ao lado e só então a renomeia para o nome final."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.parent / f".{target.name}.partial-{os.getpid()}"
    if partial.exists():
        shutil.rmtree(partial)
    data = git(repo, "archive", "--format=tar", tag, binary=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(partial, filter="data")
        meta = {"tag": tag, "commit": commit, "source": str(repo),
                "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        (partial / "RELEASE.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        os.rename(partial, target)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise


def check_release(target: Path, tag: str, commit: str) -> None:
    try:
        meta = json.loads((target / "RELEASE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ReleaseError(f"{target} existe mas não é uma versão extraída por este script") from None
    if meta.get("tag") != tag or meta.get("commit") != commit:
        raise ReleaseError(f"{target} não corresponde à tag {tag} ({commit[:8]}); não foi alterada")


def installed_location(home: Path) -> Path | None:
    try:
        return Path(json.loads((home / LOCATION).read_text(encoding="utf-8"))["harnessctl"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def same(a: Path | None, b: Path) -> bool:
    return a is not None and os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def point_current(releases: Path, target: Path) -> None:
    link = releases / "current"
    if link.exists() or link.is_symlink() or os.path.isjunction(link):
        if os.path.isjunction(link):
            os.rmdir(link)  # remove só o atalho, não a pasta de destino
        elif link.is_symlink():
            link.unlink()
        else:
            raise ReleaseError(f"{link} existe e não é um atalho; não foi alterado")
    if os.name == "nt":
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                              capture_output=True, check=False)
        if proc.returncode != 0:
            raise ReleaseError("não foi possível criar o atalho current")
    else:
        os.symlink(target, link, target_is_directory=True)


def install(tag: str, home: Path | None = None, releases: Path | None = None, source_repo: Path = ROOT,
            apply: bool = False) -> dict:
    home = (home or Path.home()).absolute()
    releases = (releases or home / ".harness-engineering").absolute()
    commit = tag_commit(source_repo, tag)
    target = releases / tag
    new_ctl = target / "scripts" / "harnessctl.py"
    old_ctl = installed_location(home)
    plan = {"tag": tag, "commit": commit, "release_dir": str(target), "current": str(releases / "current"),
            "previous": str(old_ctl) if old_ctl else None}
    if not apply:
        steps = [f"extrair {tag} em {target}" if not target.exists() else f"conferir {target}"]
        if old_ctl and not same(old_ctl, new_ctl):
            steps.append(f"machine-remove com {old_ctl}")
        steps += [f"machine-install e machine-verify com {new_ctl}", f"apontar {releases / 'current'}"]
        return {"status": "PLANNED", **plan, "steps": steps}

    if target.exists():
        check_release(target, tag, commit)
    else:
        export(source_repo, tag, commit, target)

    if same(old_ctl, new_ctl):
        harnessctl(new_ctl, "machine-verify", home=home)
        point_current(releases, target)
        return {"status": "ALREADY_CURRENT", **plan}

    if old_ctl is not None:
        if not old_ctl.is_file():
            raise ReleaseError(f"o instalador anterior não existe mais ({old_ctl}); restaure-o ou remova à mão")
        harnessctl(old_ctl, "machine-remove", "--apply", home=home)
    try:
        harnessctl(new_ctl, "machine-install", "--apply", home=home)
        harnessctl(new_ctl, "machine-verify", home=home)
    except BaseException:
        if old_ctl is not None:  # volta ao que estava instalado
            try:
                harnessctl(new_ctl, "machine-remove", "--apply", home=home)
            except ReleaseError:
                pass
            harnessctl(old_ctl, "machine-install", "--apply", home=home)
        raise
    point_current(releases, target)
    return {"status": "INSTALLED", **plan}


def status(home: Path | None = None, releases: Path | None = None) -> dict:
    home = (home or Path.home()).absolute()
    releases = (releases or home / ".harness-engineering").absolute()
    loc = installed_location(home)
    out: dict = {"installed_from": str(loc) if loc else None, "release": None, "machine_verify": None,
                 "current": None}
    link = releases / "current"
    if link.exists():
        out["current"] = str(link.resolve())
    if loc is not None:
        try:
            out["release"] = json.loads((loc.parents[1] / "RELEASE.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out["release"] = "NOT_A_RELEASE_DIR"  # instalado de uma pasta de desenvolvimento
        try:
            out["machine_verify"] = harnessctl(loc, "machine-verify", home=home)["status"]
        except ReleaseError as exc:
            out["machine_verify"] = f"BLOCKED: {exc}"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    p_install = sub.add_parser("install", help="instalar ou atualizar a partir de uma tag")
    p_install.add_argument("--tag", required=True)
    p_install.add_argument("--apply", action="store_true", help="sem isto, só mostra o plano")
    p_status = sub.add_parser("status", help="de onde está instalado e se confere")
    for p in (p_install, p_status):
        p.add_argument("--home", type=Path, help="padrão: a home do usuário")
        p.add_argument("--releases", type=Path, help="padrão: ~/.harness-engineering")
    p_install.add_argument("--source-repo", type=Path, default=ROOT, help="repositório Git com a tag")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.action == "install":
            result = install(args.tag, args.home, args.releases, args.source_repo, apply=args.apply)
        else:
            result = status(args.home, args.releases)
    except ReleaseError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
