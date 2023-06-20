
import * as esb from 'esbuild'
const isServe = process.argv.includes('--serve')
const watch = isServe || process.argv.includes('--watch')
const prod = process.argv.includes('--prod')

if (prod && isServe) {
    throw new Error('--serve and --prod cannot be used together')
}


function watcher(item) {
    function onRebuild(error, result) {
        if (error) { console.error(`watch build ${item} failed:`, error) }
        else { console.log('built', item) }
    }
    return { onRebuild }
}


esb.build({
    logLevel: 'info',
    entryPoints: ['./src/extension.ts'],
    bundle: true,
    outfile: 'out/main.js',
    external: ['vscode'],
    format: "cjs",
    platform: 'node',
    sourcemap: !prod,
    watch: watch && watcher('extension'),
})
