/**
 * Wrapper Node para invocar Calculator.predictWinner() y predictWinner3Way()
 * desde el test de paridad (tests/test_consistency.py).
 *
 * Uso (un caso a la vez via stdin):
 *   echo '{"home": {...}, "away": {...}}' | node tests/run_calculator.js
 *
 * Lee JSON con {home, away} de stdin, ejecuta ambas funciones,
 * imprime JSON resultado a stdout: {predictWinner: {...}, predictWinner3Way: {...}}
 */

// El navegador define `window` y `DataLoader`. En Node necesitamos stubs
// porque calculator.js usa DataLoader.parsePercentage() en predictGoals/BTTS
// (aunque nuestras 2 funciones bajo test no lo usen). Stub mínimo:
global.window = {};
global.DataLoader = {
    parsePercentage: (s) => {
        if (s === null || s === undefined) return 0;
        if (typeof s === 'number') return s;
        const m = String(s).match(/(-?\d+\.?\d*)/);
        return m ? parseFloat(m[1]) : 0;
    },
};

// Cargar calculator.js (via require después de los stubs)
const path = require('path');
const calculatorPath = path.resolve(__dirname, '..', 'js', 'calculator.js');
const { Calculator } = require(calculatorPath);

// Leer todo stdin
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
    try {
        const payload = JSON.parse(input);
        const { home, away } = payload;

        const winnerResult = Calculator.predictWinner(home, away, 'HOME', 'AWAY');
        const threeWayResult = Calculator.predictWinner3Way(home, away);

        const output = {
            predictWinner:     winnerResult,
            predictWinner3Way: threeWayResult,
        };

        process.stdout.write(JSON.stringify(output));
    } catch (err) {
        console.error('ERROR en run_calculator.js:', err.message);
        process.exit(1);
    }
});
