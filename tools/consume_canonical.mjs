// No network: stdin/file input, stdout output only.
import fs from 'node:fs';
import dgram from 'node:dgram';
import { consumeCanonical } from '../src/ruview_offline.mjs';
dgram.createSocket = () => { throw new Error('UDP forbidden in offline consumer'); };
const source = process.argv[2] ?? '-';
const canonical = JSON.parse(fs.readFileSync(source === '-' ? 0 : source,'utf8'));
process.stdout.write(JSON.stringify(consumeCanonical(canonical))+'\n');
