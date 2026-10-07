// ESLint 9 flat config (SDK 57). See eslint-config-expo/flat.js.
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([...expoConfig, { ignores: ['dist/*'] }]);
