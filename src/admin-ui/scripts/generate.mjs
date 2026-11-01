import openapiTS, { astToString } from 'openapi-typescript'

const schema = new URL('../../../features/ui_flows/openapi.json', import.meta.url)
const target = new URL('../src/generated/api.d.ts', import.meta.url)
const content = astToString(await openapiTS(schema, { defaultNonNullable: false }))
if (Bun.argv.includes('--check')) {
  if ((await Bun.file(target).text()) !== content)
    throw new Error('Run bun run generate: API types are stale')
} else {
  await Bun.write(target, content)
}
