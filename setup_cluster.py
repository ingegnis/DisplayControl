#!/usr/bin/env python3
"""Create private Core/coordinator configuration bundles without touching system settings."""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from cluster import endpoint


def provision(core_a, core_b, coordinator, destination):
    nodes = {'core-a': endpoint(core_a), 'core-b': endpoint(core_b)}
    coordinator = endpoint(coordinator)
    if len(set([*nodes.values(), coordinator])) != 3:
        raise ValueError('Usa tre indirizzi distinti per i due Core e il coordinatore.')
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if any((destination / name).exists() for name in ('core-a', 'core-b', 'coordinator')):
        raise ValueError('La destinazione contiene già una configurazione. Scegli una nuova cartella.')
    key = secrets.token_urlsafe(48)
    shared = {'key': key, 'nodes': nodes, 'coordinator': coordinator, 'initialPrimary': 'core-a',
              'oscPorts': {'core-a': 9001, 'core-b': 9001}}
    result = []
    for name in ('core-a', 'core-b', 'coordinator'):
        folder = destination / name
        folder.mkdir(mode=0o700)
        config = folder / 'cluster.json'
        config.write_text(json.dumps(dict(shared, node=name), indent=2) + '\n', encoding='utf-8')
        try:
            config.chmod(0o600)
        except OSError:
            pass
        port = urlsplit(coordinator if name == 'coordinator' else nodes[name]).port or (443 if urlsplit(coordinator if name == 'coordinator' else nodes[name]).scheme == 'https' else 80)
        command = ('coordinator.py --config data/cluster.json' if name == 'coordinator'
                   else 'server.py --cluster-config data/cluster.json --prompt-osc-bind 0.0.0.0 --prompt-osc-port 9001')
        (folder / 'START.txt').write_text(
            'PRIVATE CLUSTER CONFIGURATION — DO NOT PUBLISH\n\n'
            '1. Copy DisplayControl to this machine.\n'
            '2. Copy cluster.json into its private data/ folder.\n'
            f'3. Run: python {command} --host 0.0.0.0 --port {port}\n\n'
            'Start both Cores, then the coordinator. Open the coordinator URL on all consoles/players.\n'
            'Core A provides the administrator key; the private HA copy preserves that identity.\n'
            'Use a trusted LAN, synchronized clocks, separate power and an appropriate UPS.\n'
            'The coordinator stores private credentials and recovery data; protect its data directory.\n'
            'HTTP is not encrypted; add locally managed TLS if required.\n', encoding='utf-8')
        result.append(folder)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-a', required=True)
    parser.add_argument('--core-b', required=True)
    parser.add_argument('--coordinator', required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'data/cluster-setup')
    args = parser.parse_args()
    try:
        folders = provision(args.core_a, args.core_b, args.coordinator, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print('Configurazioni private create:')
    for folder in folders:
        print(folder)
    print('Distribuisci solo il bundle della macchina corretta. Istruzioni in START.txt e docs/CLUSTER.md.')


if __name__ == '__main__':
    main()
