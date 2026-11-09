<?php
declare(strict_types=1);

// Native runner for the scenarios and assertions from the original Python suite.
function valueAt(mixed $value, string $path): mixed
{
    foreach ($path === '' ? [] : explode('.', $path) as $part) {
        if (is_array($value) && array_key_exists($part, $value)) $value = $value[$part];
        elseif ($value instanceof stdClass && property_exists($value, $part)) $value = $value->$part;
        else throw new RuntimeException("Missing path: $path");
    }
    return $value;
}

function sameValue(mixed $a, mixed $b): bool
{
    if ($a instanceof stdClass && $b instanceof stdClass) {
        $a = get_object_vars($a);
        $b = get_object_vars($b);
        if (count($a) !== count($b)) return false;
        foreach ($a as $key => $value) {
            if (!array_key_exists($key, $b) || !sameValue($value, $b[$key])) return false;
        }
        return true;
    }
    if (is_array($a) && is_array($b)) {
        if (array_keys($a) !== array_keys($b)) return false;
        foreach ($a as $key => $value) if (!sameValue($value, $b[$key])) return false;
        return true;
    }
    return $a === $b;
}

function checkValue(mixed $value, object $spec): bool
{
    switch ($spec->op) {
        case 'equals': return sameValue($value, $spec->expected);
        case 'at': return sameValue(valueAt($value, $spec->path), $spec->expected);
        case 'contains':
            if (is_string($value)) return str_contains($value, $spec->expected);
            if ($value instanceof stdClass) return property_exists($value, $spec->expected);
            foreach ($value as $item) if (sameValue($item, $spec->expected)) return true;
            return false;
        case 'count':
            $current = valueAt($value, $spec->path);
            $count = is_string($current) ? strlen($current) : count((array) $current);
            return $count === $spec->expected;
        case 'any':
            foreach (valueAt($value, $spec->path) as $item) if (checkValue($item, $spec->check)) return true;
            return false;
        case 'all':
            foreach ($spec->checks as $check) if (!checkValue($value, $check)) return false;
            return true;
        default: throw new RuntimeException('Unknown assertion: ' . $spec->op);
    }
}

function runSuite(): int
{
    $root = dirname(__DIR__, 2);
    $suite = json_decode(file_get_contents($root . '/tests/fixtures/scenarios.json'), false, 512, JSON_THROW_ON_ERROR);
    $passing = [];
    foreach ($suite->cases as $case) {
        $label = $case->article . ' / ' . $case->name;
        $inputPath = null;
        try {
            $input = unserialize(serialize($suite->base_input));
            foreach ($case->patches as $patch) {
                $current = $input;
                $parts = $patch->path;
                $key = array_pop($parts);
                foreach ($parts as $part) $current = $current->$part;
                if ($patch->remove ?? false) unset($current->$key);
                else $current->$key = $patch->value;
            }
            // Use a file as Python does, avoiding pipe deadlocks on Windows.
            $inputPath = tempnam(sys_get_temp_dir(), 'gdpr_');
            if ($inputPath === false) throw new RuntimeException('Could not create temporary input');
            if (file_put_contents($inputPath, json_encode($input, JSON_THROW_ON_ERROR)) === false) {
                throw new RuntimeException('Could not write temporary input');
            }
            $out = tmpfile();
            $err = tmpfile();
            if ($out === false || $err === false) throw new RuntimeException('Could not create output streams');
            try {
                $process = proc_open(['opa', 'eval', '--format', 'json', '--data', $root . '/gdpr',
                    '--input', $inputPath, $case->expr], [0 => ['file', $inputPath, 'r'], 1 => $out, 2 => $err],
                    $pipes, $root, null, ['bypass_shell' => true, 'create_no_window' => true]);
                if (!is_resource($process)) throw new RuntimeException('Could not start OPA');
                $status = proc_close($process);
                rewind($out);
                rewind($err);
                $stdout = stream_get_contents($out);
                $stderr = stream_get_contents($err);
                if ($status !== 0) throw new RuntimeException($stderr ?: $stdout);
                $payload = json_decode($stdout, false, 512, JSON_THROW_ON_ERROR);
            } finally {
                fclose($out);
                fclose($err);
            }
            $value = $payload->result[0]->expressions[0]->value ?? null;
            if (!checkValue($value, $case->expect)) {
                throw new RuntimeException('expr=' . $case->expr . '; value=' . json_encode($value));
            }
            echo "PASS $label\n";
            $passing[] = $case;
        } catch (Throwable $error) {
            fwrite(STDERR, "FAIL $label: " . $error->getMessage() . "\n");
        } finally {
            if (is_string($inputPath) && is_file($inputPath)) unlink($inputPath);
        }
    }
    echo "\nResult: " . count($passing) . '/' . count($suite->cases) . " passed\n";
    echo "\nScenario coverage checklist:\n";
    $covered = 0;
    foreach ($suite->coverage as $item) {
        $ok = false;
        foreach ($passing as $case) {
            if ($case->article !== $item->article) continue;
            $haystack = strtolower($case->name . ' ' . $case->expr);
            $matches = true;
            foreach ($item->terms as $term) if (!str_contains($haystack, strtolower($term))) $matches = false;
            if ($matches) { $ok = true; break; }
        }
        echo ($ok ? 'PASS ' : 'MISS ') . "$item->article / $item->kind / $item->label\n";
        if ($ok) $covered++;
    }
    echo "\nScenario coverage result: $covered/" . count($suite->coverage) . " expected items covered\n";
    return count($passing) === count($suite->cases) && $covered === count($suite->coverage) ? 0 : 1;
}

try {
    exit(runSuite());
} catch (Throwable $error) {
    fwrite(STDERR, $error->getMessage() . "\n");
    exit(1);
}
