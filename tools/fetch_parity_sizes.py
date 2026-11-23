#!/usr/bin/env python3
"""Record npm unpacked sizes and Maven Central jar sizes for the migration pages.

Production dependencies only. Dev, optional, and peer dependencies are not
walked. Packages are deduped by name. Versions are each registry's latest
published release for npm, and the versions named below for Maven.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "parity-sizes.json"
UA = "crocket-site-parity/1.0"
NS = {"m": "http://maven.apache.org/POM/4.0.0"}

NPM_DIRECT = [
    ("express", "The framework"),
    ("zod", "JSON validation"),
    ("express-oauth2-jwt-bearer", "JWT and OIDC"),
    ("prom-client", "Prometheus metrics"),
    ("express-prom-bundle", "Prometheus metrics"),
    ("pino", "Structured logging"),
    ("pino-http", "Structured logging"),
    ("swagger-jsdoc", "OpenAPI"),
    ("swagger-ui-express", "OpenAPI"),
    ("helmet", "Security headers"),
    ("cors", "CORS"),
    ("@grpc/grpc-js", "gRPC"),
    ("@grpc/proto-loader", "gRPC"),
]

# springdoc 3.x tracks Spring Boot 4. 2.8.16 is the latest 2.8, for Boot 3.
MAVEN_DIRECT = [
    ("org.springframework.boot", "spring-boot-starter-web", "3.5.0", "HTTP and JSON"),
    ("org.springframework.boot", "spring-boot-starter-validation", "3.5.0", "JSON validation"),
    ("org.springframework.boot", "spring-boot-starter-security", "3.5.0", "Security headers"),
    (
        "org.springframework.boot",
        "spring-boot-starter-oauth2-resource-server",
        "3.5.0",
        "JWT and OIDC",
    ),
    ("org.springframework.boot", "spring-boot-starter-actuator", "3.5.0", "Metrics"),
    ("io.micrometer", "micrometer-registry-prometheus", None, "Prometheus metrics"),
    (
        "org.springdoc",
        "springdoc-openapi-starter-webmvc-ui",
        "2.8.16",
        "OpenAPI",
    ),
    ("net.devh", "grpc-spring-boot-starter", "3.1.0.RELEASE", "gRPC"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            return res.read(), res.headers.get("Content-Length")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None, None
        raise


def head_length(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            length = res.headers.get("Content-Length")
            return int(length) if length else None
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise


def unpacked_from_tarball(url):
    """Sum of member sizes. Used when the registry omits dist.unpackedSize."""
    if not url:
        raise SystemExit("npm package has no tarball")
    body, _ = get(url)
    total = 0
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                total += member.size
    return total, "tarball member sizes"


def npm_doc(name):
    quoted = urllib.request.quote(name, safe="")
    body, _ = get(f"https://registry.npmjs.org/{quoted}/latest")
    if body is None:
        raise SystemExit(f"npm package not found: {name}")
    return json.loads(body)


def npm_tree():
    seen = {}
    missing = []

    def walk(name, direct):
        if name in seen:
            if direct:
                seen[name]["direct"] = True
            return
        doc = npm_doc(name)
        dist = doc.get("dist") or {}
        size = dist.get("unpackedSize")
        source = "registry unpackedSize"
        if size is None:
            missing.append(name)
            size, source = unpacked_from_tarball(dist.get("tarball"))
        seen[name] = {
            "name": name,
            "version": doc.get("version"),
            "unpacked_bytes": size,
            "size_source": source,
            "direct": direct,
        }
        bundled = set(doc.get("bundleDependencies") or doc.get("bundledDependencies") or [])
        deps = doc.get("dependencies") or {}
        for child in deps:
            if child in bundled:
                continue
            walk(child, False)

    for name, _why in NPM_DIRECT:
        walk(name, True)
    packages = sorted(seen.values(), key=lambda row: (not row["direct"], row["name"]))
    return {
        "registry": "https://registry.npmjs.org/<name>/latest",
        "method": (
            "latest published version of each package; production dependencies only; "
            "dev, optional, and peer dependencies are not walked; bundled dependencies "
            "stay inside the parent's unpacked size; deduped by package name"
        ),
        "direct": [{"name": name, "feature": why} for name, why in NPM_DIRECT],
        "packages": packages,
        "missing_unpacked_size": missing,
        "direct_count": sum(1 for row in packages if row["direct"]),
        "package_count": len(packages),
        "total_unpacked_bytes": sum(row["unpacked_bytes"] for row in packages),
    }


def text_of(el):
    return (el.text or "").strip() if el is not None else ""


def children(el, tag):
    if el is None:
        return []
    found = el.findall(f"m:{tag}", NS)
    return found if found else el.findall(tag)


def child(el, tag):
    items = children(el, tag)
    return items[0] if items else None


class Maven:
    def __init__(self):
        self.poms = {}
        self.jar_bytes = {}

    def pom(self, g, a, v):
        key = (g, a, v)
        if key not in self.poms:
            path = g.replace(".", "/")
            url = f"https://repo1.maven.org/maven2/{path}/{a}/{v}/{a}-{v}.pom"
            body, _ = get(url)
            if body is None:
                raise SystemExit(f"pom not found: {g}:{a}:{v}")
            self.poms[key] = ET.fromstring(body)
        return self.poms[key]

    def jar(self, g, a, v):
        key = (g, a, v)
        if key not in self.jar_bytes:
            path = g.replace(".", "/")
            url = f"https://repo1.maven.org/maven2/{path}/{a}/{v}/{a}-{v}.jar"
            _body, length = get(url)
            self.jar_bytes[key] = int(length) if length else None
        return self.jar_bytes[key]

    def props(self, g, a, v, stack):
        if (g, a, v) in stack:
            return {}
        root = self.pom(g, a, v)
        merged = {}
        parent = child(root, "parent")
        if parent is not None:
            pg = text_of(child(parent, "groupId"))
            pa = text_of(child(parent, "artifactId"))
            pv = text_of(child(parent, "version"))
            merged.update(self.props(pg, pa, pv, stack | {(g, a, v)}))
            merged["project.parent.groupId"] = pg
            merged["project.parent.artifactId"] = pa
            merged["project.parent.version"] = self.expand(pv, merged)
        props_el = child(root, "properties")
        if props_el is not None:
            for prop in list(props_el):
                tag = prop.tag.split("}")[-1]
                merged[tag] = text_of(prop)
        gid = text_of(child(root, "groupId")) or merged.get("project.groupId", "")
        merged["project.groupId"] = self.expand(gid, merged) if gid else ""
        merged["project.artifactId"] = a
        merged["project.version"] = v
        merged["pom.version"] = v
        return merged

    def expand(self, value, props, limit=12):
        if value is None:
            return None
        out = value
        for _ in range(limit):
            start = out.find("${")
            if start < 0:
                return out
            end = out.find("}", start)
            if end < 0:
                return out
            key = out[start + 2 : end]
            repl = props.get(key)
            if repl is None:
                return out
            out = out[:start] + repl + out[end + 1 :]
        return out

    def managed(self, g, a, v, stack=None):
        """Map (group, artifact) to version string, child overriding parent."""
        stack = stack or set()
        if (g, a, v) in stack:
            return {}
        root = self.pom(g, a, v)
        props = self.props(g, a, v, set())
        found = {}
        parent = child(root, "parent")
        if parent is not None:
            found.update(
                self.managed(
                    text_of(child(parent, "groupId")),
                    text_of(child(parent, "artifactId")),
                    text_of(child(parent, "version")),
                    stack | {(g, a, v)},
                )
            )
        dm = child(root, "dependencyManagement")
        for dep in children(child(dm, "dependencies"), "dependency"):
            scope = text_of(child(dep, "scope")) or "compile"
            typ = text_of(child(dep, "type")) or "jar"
            dg = self.expand(text_of(child(dep, "groupId")) or props.get("project.groupId", ""), props)
            da = self.expand(text_of(child(dep, "artifactId")), props)
            dv = self.expand(text_of(child(dep, "version")), props)
            if scope == "import" and typ == "pom" and dv:
                found.update(self.managed(dg, da, dv, stack | {(g, a, v)}))
                continue
            if dv:
                found[(dg, da)] = dv
        return found

    def deps_of(self, g, a, v, managed_versions):
        root = self.pom(g, a, v)
        props = self.props(g, a, v, set())
        out = []
        for dep in children(child(root, "dependencies"), "dependency"):
            optional = text_of(child(dep, "optional")) == "true"
            if optional:
                continue
            scope = text_of(child(dep, "scope")) or "compile"
            typ = text_of(child(dep, "type")) or "jar"
            if scope in {"test", "provided", "system"}:
                continue
            dg = self.expand(text_of(child(dep, "groupId")) or props.get("project.groupId", ""), props)
            da = self.expand(text_of(child(dep, "artifactId")), props)
            dv = self.expand(text_of(child(dep, "version")) or None, props)
            if not dv:
                dv = managed_versions.get((dg, da))
            if not dv:
                raise SystemExit(f"no version for {dg}:{da} required by {g}:{a}:{v}")
            out.append((dg, da, dv, scope, typ))
        return out

    def tree(self):
        # One managed set: Boot's BOM, then each direct POM's own management.
        boot = self.managed(
            "org.springframework.boot", "spring-boot-dependencies", "3.5.0"
        )
        directs = []
        for g, a, v, why in MAVEN_DIRECT:
            version = v or boot.get((g, a))
            if not version:
                raise SystemExit(f"no BOM version for {g}:{a}")
            directs.append((g, a, version, why))
        seen = {}

        def walk(g, a, v, direct, why):
            key = f"{g}:{a}"
            if key in seen:
                if direct:
                    seen[key]["direct"] = True
                    seen[key]["feature"] = why
                return
            managed = dict(boot)
            managed.update(self.managed(g, a, v))
            size = None
            if self.pom_packaging(g, a, v) != "pom":
                path = g.replace(".", "/")
                url = f"https://repo1.maven.org/maven2/{path}/{a}/{v}/{a}-{v}.jar"
                size = head_length(url)
            seen[key] = {
                "group": g,
                "artifact": a,
                "version": v,
                "jar_bytes": size,
                "direct": direct,
                "feature": why if direct else "",
                "packaging": self.pom_packaging(g, a, v),
            }
            for dg, da, dv, scope, typ in self.deps_of(g, a, v, managed):
                if scope == "import" and typ == "pom":
                    continue
                walk(dg, da, dv, False, "")

        for g, a, v, why in directs:
            walk(g, a, v, True, why)
        artifacts = sorted(seen.values(), key=lambda row: (not row["direct"], row["group"], row["artifact"]))
        missing = [f"{r['group']}:{r['artifact']}" for r in artifacts if r["packaging"] != "pom" and not r["jar_bytes"]]
        total = sum(r["jar_bytes"] or 0 for r in artifacts)
        return {
            "repository": "https://repo1.maven.org/maven2",
            "method": (
                "jar Content-Length from Maven Central; compile and runtime dependencies; "
                "test, provided, optional, and BOM imports excluded; versions from "
                "spring-boot-dependencies 3.5.0 when a POM omits one; deduped by group:artifact. "
                "springdoc 2.8.16 is the latest 2.8 release (3.x targets Spring Boot 4)."
            ),
            "direct": [
                {"group": g, "artifact": a, "version": v, "feature": why} for g, a, v, why in directs
            ],
            "artifacts": artifacts,
            "missing_jars": missing,
            "direct_count": sum(1 for row in artifacts if row["direct"]),
            "artifact_count": sum(1 for row in artifacts if row["packaging"] != "pom" and row["jar_bytes"]),
            "pom_only_count": sum(1 for row in artifacts if row["packaging"] == "pom"),
            "total_jar_bytes": total,
        }

    def pom_packaging(self, g, a, v):
        root = self.pom(g, a, v)
        return text_of(child(root, "packaging")) or "jar"


def main():
    print("npm...", file=sys.stderr)
    npm = npm_tree()
    print(f"  {npm['package_count']} packages, {npm['total_unpacked_bytes']} bytes", file=sys.stderr)
    print("maven...", file=sys.stderr)
    maven = Maven().tree()
    print(f"  {maven['artifact_count']} jars, {maven['total_jar_bytes']} bytes", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched": "2026-11-23",
        "npm": npm,
        "maven": maven,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
