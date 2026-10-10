// Generates src/types/contract.ts from contract/schemas/. Run: npm run gen:types
// Never hand-edit the output; rerun this script when the contract changes.
import { readdirSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript'

const here = dirname(fileURLToPath(import.meta.url))
const schemasDir = resolve(here, '../../contract/schemas')
const outFile = resolve(here, '../src/types/contract.ts')

// One root schema that references every contract schema, so each named type
// is declared exactly once even when several schemas share it.
const files = readdirSync(schemasDir).filter((f) => f.endsWith('.schema.json')).sort()
const root = {
  title: 'ContractRoot',
  type: 'object',
  additionalProperties: false,
  properties: Object.fromEntries(files.map((f) => [f.replace('.schema.json', ''), { $ref: f }])),
}

const ts = await compile(root, 'ContractRoot', {
  cwd: schemasDir,
  bannerComment:
    '/* Generated from contract/schemas/ by scripts/gen-types.mjs. Do not edit by hand. */',
  additionalProperties: false,
  unreachableDefinitions: false,
})

mkdirSync(dirname(outFile), { recursive: true })
writeFileSync(outFile, ts)
console.log(`wrote ${join('src', 'types', 'contract.ts')} from ${files.length} schemas`)
