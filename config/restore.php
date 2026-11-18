<?php
// Applies /tmp/server.json (a copy of config/server.json) to this server: installs missing
// imported plugins, applies settings, and rebuilds the device and playlists.
// Secrets are not in the file; plugins that need one are listed at the end.
// Run through `make config-restore`, which deploys the custom plugins first.
use App\Models\{Device, Playlist, PlaylistItem, Plugin, User};
use App\Services\PluginImportService;
use Illuminate\Support\Str;

$config = json_decode(file_get_contents('/tmp/server.json'), true, 512, JSON_THROW_ON_ERROR);
$user = User::first() ?? exit("Register the account in the admin UI first, then run this again.\n");
if (! empty($config['timezone'])) {
    $user->update(['timezone' => $config['timezone']]);
}

$needSecrets = [];
foreach ($config['plugins'] as $entry) {
    $plugin = Plugin::where('user_id', $user->id)->where('name', $entry['name'])->first();
    if (! $plugin) {
        if (empty($entry['source']['zip_url'])) {
            echo "SKIPPED {$entry['name']}: not installed and has no download source\n";

            continue;
        }
        try {
            $plugin = app(PluginImportService::class)->importFromUrl(
                $entry['source']['zip_url'], $user, $entry['source']['zip_entry_path'] ?? null, null, null, false
            );
        } catch (Throwable $e) {
            echo "FAILED {$entry['name']}: {$e->getMessage()}\n";

            continue;
        }
        $plugin = Plugin::findOrFail($plugin->id); // drop the importer's unsaved extra attributes
        echo "INSTALLED {$entry['name']}\n";
    }
    $plugin->fill([
        'name' => $entry['name'],
        'configuration' => array_merge($plugin->configuration ?? [], (array) $entry['settings']),
        'data_stale_minutes' => $entry['data_stale_minutes'],
    ] + ($entry['polling'] ?? []))->save();
    foreach ($entry['secrets'] as $key) {
        if (empty($plugin->configuration[$key])) {
            $needSecrets[] = "{$entry['name']}: {$key}";
        }
    }
}

if (! empty($config['device'])) {
    $device = Device::where('user_id', $user->id)->where('name', $config['device']['name'])->first()
        ?? Device::create(['user_id' => $user->id, 'api_key' => Str::random(22), 'friendly_id' => Str::upper(Str::random(6))] + $config['device']);
    foreach ($config['playlists'] as $entry) {
        $playlist = Playlist::firstOrCreate(['device_id' => $device->id, 'name' => $entry['name']]);
        $playlist->update(['is_active' => $entry['is_active'], 'refresh_time' => $entry['refresh_time']]);
        foreach ($entry['items'] as $order => $item) {
            $plugin = Plugin::where('user_id', $user->id)->where('name', $item['plugin'])->first();
            if ($plugin) {
                PlaylistItem::updateOrCreate(
                    ['playlist_id' => $playlist->id, 'plugin_id' => $plugin->id],
                    ['order' => $order + 1, 'is_active' => $item['is_active']]
                );
            }
        }
    }
}

echo "RESTORED ".count($config['plugins'])." plugins\n";
foreach ($needSecrets as $line) {
    echo "NEEDS SECRET {$line}\n";
}
