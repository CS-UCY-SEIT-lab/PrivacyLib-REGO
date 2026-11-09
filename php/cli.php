<?php
declare(strict_types=1);
require_once __DIR__ . '/src/GdprRouter.php';

try {
    if (!isset($argv[1])) throw new InvalidArgumentException('Usage: php php/cli.php <policy> [input.json] [userId]');
    $file = $argv[2] ?? __DIR__ . '/../gdpr/input.json';
    $raw = file_get_contents($file);
    if ($raw === false) throw new RuntimeException('Could not read input file');
    $input = json_decode(preg_replace('/^\xEF\xBB\xBF/', '', $raw), false, 512, JSON_THROW_ON_ERROR);
    if (!$input instanceof stdClass) throw new InvalidArgumentException('input must be a JSON object');
    $result = (new GdprRouter())->route($argv[1], $input, $argv[3] ?? null);
    echo json_encode($result, JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR) . PHP_EOL;
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . PHP_EOL);
    exit(1);
}
