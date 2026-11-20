'use strict';

/*
 * Docker Volumes: Event-driven Storage Management
 *
 * Covers:
 * - Named and anonymous volumes
 * - Bind mounts
 * - Container writable layers
 * - Mount validation
 * - Shared storage
 * - Read-only policies
 * - Volume lifecycle
 * - Backup and restoration
 * - Storage cleanup
 *
 * Run: node docker_volumes.js
 */

const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const EventEmitter = require('node:events');

class StorageError extends Error {}
class ValidationError extends StorageError {}
class PolicyError extends StorageError {}
class NotFoundError extends StorageError {}

const MountType = Object.freeze({
    NAMED: 'named',
    ANONYMOUS: 'anonymous',
    BIND: 'bind'
});

const ContainerState = Object.freeze({
    CREATED: 'created',
    RUNNING: 'running',
    STOPPED: 'stopped',
    REMOVED: 'removed'
});

function validateName(name) {
    if (
        typeof name !== 'string' ||
        !/^[a-zA-Z0-9_.-]{1,128}$/.test(name)
    ) {
        throw new ValidationError('Invalid storage name.');
    }
}

function validateTarget(target) {
    if (
        typeof target !== 'string' ||
        !path.posix.isAbsolute(target) ||
        target.split('/').includes('..')
    ) {
        throw new ValidationError(
            'Mount target must be an absolute safe container path.'
        );
    }

    if (target.includes('\0')) {
        throw new ValidationError('Null bytes are not permitted.');
    }
}

class StorageManager extends EventEmitter {
    constructor(root) {
        super();

        this.root = root;
        this.volumes = new Map();
        this.containers = new Map();
        this.operationQueue = Promise.resolve();
    }

    async initialize() {
        await fs.mkdir(this.root, { recursive: true });

        this.volumesDirectory = path.join(this.root, 'volumes');
        this.backupDirectory = path.join(this.root, 'backups');

        await fs.mkdir(this.volumesDirectory, { recursive: true });
        await fs.mkdir(this.backupDirectory, { recursive: true });

        return this;
    }

    async exclusive(operation) {
        const current = this.operationQueue.then(operation);

        // Keep the queue usable after a failed operation.
        this.operationQueue = current.catch(() => {});

        return current;
    }

    emitEvent(event, details = {}) {
        this.emit(event, {
            event,
            timestamp: new Date().toISOString(),
            ...details
        });
    }

    async createVolume(name, options = {}) {
        return this.exclusive(async () => {
            const anonymous = !name;

            if (anonymous) {
                name = crypto.randomUUID().replaceAll('-', '');
            }

            validateName(name);

            if (this.volumes.has(name)) {
                throw new PolicyError(`Volume already exists: ${name}`);
            }

            const directory = path.join(
                this.volumesDirectory,
                name
            );

            await fs.mkdir(directory, { recursive: false });

            const volume = {
                name,
                type: anonymous
                    ? MountType.ANONYMOUS
                    : MountType.NAMED,
                path: directory,
                labels: Object.freeze({ ...options.labels }),
                readOnly: false,
                references: new Set(),
                createdAt: new Date().toISOString()
            };

            this.volumes.set(name, volume);

            this.emitEvent('volume.created', { name, type: volume.type });

            return volume;
        });
    }

    async createBindMount(name, source, options = {}) {
        return this.exclusive(async () => {
            validateName(name);

            if (this.volumes.has(name)) {
                throw new PolicyError('Storage name already exists.');
            }

            const resolved = await fs.realpath(source);
            const info = await fs.stat(resolved);

            if (!info.isDirectory()) {
                throw new ValidationError(
                    'Bind mount source must be a directory.'
                );
            }

            const volume = {
                name,
                type: MountType.BIND,
                path: resolved,
                readOnly: Boolean(options.readOnly),
                references: new Set(),
                labels: Object.freeze({}),
                createdAt: new Date().toISOString()
            };

            this.volumes.set(name, volume);

            this.emitEvent('bind.created', { name, source: resolved });

            return volume;
        });
    }

    async createContainer(name, mountSpecs) {
        return this.exclusive(async () => {
            validateName(name);

            if (this.containers.has(name)) {
                throw new PolicyError('Container already exists.');
            }

            if (!Array.isArray(mountSpecs)) {
                throw new ValidationError('Mount specifications must be an array.');
            }

            const destinations = new Set();
            const mounts = [];

            for (const spec of mountSpecs) {
                const { type, source, target } = spec;

                validateTarget(target);

                if (!Object.values(MountType).includes(type)) {
                    throw new ValidationError('Invalid mount type.');
                }

                if (destinations.has(target)) {
                    throw new PolicyError('Duplicate mount destination.');
                }

                destinations.add(target);

                const volume = this.volumes.get(source);

                if (!volume || volume.type !== type) {
                    throw new NotFoundError(
                        `Storage source not found or type mismatch: ${source}`
                    );
                }

                const readOnly = Boolean(spec.readOnly);

                if (volume.readOnly && !readOnly) {
                    throw new PolicyError(
                        'Read-only storage cannot be mounted writable.'
                    );
                }

                mounts.push({
                    source,
                    target,
                    type,
                    readOnly
                });
            }

            const container = {
                name,
                state: ContainerState.CREATED,
                mounts,
                writableLayer: new Map(),
                createdAt: new Date().toISOString()
            };

            this.containers.set(name, container);

            for (const mount of mounts) {
                this.volumes.get(mount.source).references.add(name);
            }

            this.emitEvent('container.created', {
                name,
                mountCount: mounts.length
            });

            return container;
        });
    }

    getContainer(name) {
        const container = this.containers.get(name);

        if (!container || container.state === ContainerState.REMOVED) {
            throw new NotFoundError(`Container not found: ${name}`);
        }

        return container;
    }

    async startContainer(name) {
        return this.exclusive(async () => {
            const container = this.getContainer(name);

            if (container.state === ContainerState.RUNNING) {
                return container;
            }

            container.state = ContainerState.RUNNING;

            this.emitEvent('container.started', { name });

            return container;
        });
    }

    async stopContainer(name) {
        return this.exclusive(async () => {
            const container = this.getContainer(name);

            if (container.state !== ContainerState.RUNNING) {
                throw new PolicyError('Container is not running.');
            }

            container.state = ContainerState.STOPPED;

            this.emitEvent('container.stopped', { name });

            return container;
        });
    }

    resolveMount(container, containerPath) {
        validateTarget(containerPath);

        const matches = container.mounts
            .filter(mount => (
                containerPath === mount.target ||
                containerPath.startsWith(mount.target + '/')
            ))
            .sort((a, b) => b.target.length - a.target.length);

        if (matches.length === 0) {
            return null;
        }

        const mount = matches[0];
        const relative = path.posix.relative(
            mount.target,
            containerPath
        );

        const volume = this.volumes.get(mount.source);

        if (!volume) {
            throw new NotFoundError('Mounted storage no longer exists.');
        }

        const destination = path.resolve(
            volume.path,
            relative
        );

        const relativeCheck = path.relative(
            volume.path,
            destination
        );

        if (
            relativeCheck === '..' ||
            relativeCheck.startsWith('..' + path.sep) ||
            path.isAbsolute(relativeCheck)
        ) {
            throw new PolicyError('Storage path traversal detected.');
        }

        return { mount, volume, destination };
    }

    async writeFile(containerName, containerPath, content) {
        return this.exclusive(async () => {
            const container = this.getContainer(containerName);

            if (container.state !== ContainerState.RUNNING) {
                throw new PolicyError('Container must be running.');
            }

            const resolved = this.resolveMount(
                container,
                containerPath
            );

            if (!resolved) {
                container.writableLayer.set(containerPath, String(content));
                return;
            }

            const { mount, destination } = resolved;

            if (mount.readOnly) {
                throw new PolicyError('Mount is read-only.');
            }

            await fs.mkdir(path.dirname(destination), {
                recursive: true
            });

            await fs.writeFile(
                destination,
                String(content),
                { encoding: 'utf8', flag: 'w' }
            );

            this.emitEvent('storage.written', {
                containerName,
                containerPath
            });
        });
    }

    async readFile(containerName, containerPath) {
        const container = this.getContainer(containerName);

        const resolved = this.resolveMount(
            container,
            containerPath
        );

        if (!resolved) {
            if (!container.writableLayer.has(containerPath)) {
                throw new NotFoundError('Container file not found.');
            }

            return container.writableLayer.get(containerPath);
        }

        return fs.readFile(resolved.destination, 'utf8');
    }

    async inspectVolume(name) {
        const volume = this.volumes.get(name);

        if (!volume) {
            throw new NotFoundError('Volume not found.');
        }

        let sizeBytes = 0;

        if (volume.type !== MountType.BIND) {
            async function calculate(directory) {
                const entries = await fs.readdir(directory, {
                    withFileTypes: true
                });

                for (const entry of entries) {
                    const fullPath = path.join(directory, entry.name);

                    if (entry.isSymbolicLink()) {
                        continue;
                    }

                    if (entry.isDirectory()) {
                        await calculate(fullPath);
                    } else {
                        sizeBytes += (await fs.stat(fullPath)).size;
                    }
                }
            }

            await calculate(volume.path);
        }

        return {
            name: volume.name,
            type: volume.type,
            path: volume.path,
            references: [...volume.references],
            readOnly: volume.readOnly,
            sizeBytes,
            labels: volume.labels
        };
    }

    async backupVolume(name) {
        return this.exclusive(async () => {
            const volume = this.volumes.get(name);

            if (!volume) {
                throw new NotFoundError('Volume not found.');
            }

            if (volume.type === MountType.BIND) {
                throw new PolicyError(
                    'Bind mount backup requires a separate host backup policy.'
                );
            }

            const files = {};

            async function collect(directory, relative = '') {
                const entries = await fs.readdir(directory, {
                    withFileTypes: true
                });

                for (const entry of entries) {
                    const full = path.join(directory, entry.name);
                    const key = path.posix.join(relative, entry.name);

                    if (entry.isSymbolicLink()) {
                        throw new PolicyError(
                            'Symbolic links are not accepted in backups.'
                        );
                    }

                    if (entry.isDirectory()) {
                        await collect(full, key);
                    } else if (entry.isFile()) {
                        files[key] = await fs.readFile(full, 'utf8');
                    }
                }
            }

            await collect(volume.path);

            const payload = {
                volume: name,
                timestamp: new Date().toISOString(),
                files
            };

            const destination = path.join(
                this.backupDirectory,
                `${name}.json`
            );

            await fs.writeFile(
                destination,
                JSON.stringify(payload, null, 2),
                { encoding: 'utf8', flag: 'wx' }
            );

            this.emitEvent('volume.backup.created', { name });

            return destination;
        });
    }

    async restoreVolume(backupPath, destinationName) {
        return this.exclusive(async () => {
            validateName(destinationName);

            const backup = JSON.parse(
                await fs.readFile(backupPath, 'utf8')
            );

            if (
                !backup.files ||
                typeof backup.files !== 'object' ||
                Array.isArray(backup.files)
            ) {
                throw new ValidationError('Invalid backup structure.');
            }

            const volumePath = path.join(
                this.volumesDirectory,
                destinationName
            );

            if (this.volumes.has(destinationName)) {
                throw new PolicyError('Destination volume already exists.');
            }

            await fs.mkdir(volumePath);

            try {
                for (const [relative, content] of Object.entries(backup.files)) {
                    if (
                        path.posix.isAbsolute(relative) ||
                        relative.split('/').includes('..') ||
                        typeof content !== 'string'
                    ) {
                        throw new ValidationError(
                            'Invalid backup file path or content.'
                        );
                    }

                    const destination = path.resolve(
                        volumePath,
                        relative
                    );

                    const relativeCheck = path.relative(
                        volumePath,
                        destination
                    );

                    if (
                        relativeCheck === '..' ||
                        relativeCheck.startsWith('..' + path.sep) ||
                        path.isAbsolute(relativeCheck)
                    ) {
                        throw new PolicyError(
                            'Backup path escaped destination.'
                        );
                    }

                    await fs.mkdir(path.dirname(destination), {
                        recursive: true
                    });

                    await fs.writeFile(destination, content, {
                        encoding: 'utf8',
                        flag: 'wx'
                    });
                }

                this.volumes.set(destinationName, {
                    name: destinationName,
                    type: MountType.NAMED,
                    path: volumePath,
                    labels: Object.freeze({ restored: 'true' }),
                    readOnly: false,
                    references: new Set(),
                    createdAt: new Date().toISOString()
                });

                this.emitEvent('volume.restored', {
                    name: destinationName
                });

            } catch (error) {
                await fs.rm(volumePath, {
                    recursive: true,
                    force: true
                });

                throw error;
            }
        });
    }

    async removeContainer(name) {
        return this.exclusive(async () => {
            const container = this.getContainer(name);

            if (container.state === ContainerState.RUNNING) {
                container.state = ContainerState.STOPPED;
            }

            for (const mount of container.mounts) {
                this.volumes.get(mount.source).references.delete(name);
            }

            container.writableLayer.clear();
            container.state = ContainerState.REMOVED;

            this.emitEvent('container.removed', { name });
        });
    }

    async removeVolume(name, options = {}) {
        return this.exclusive(async () => {
            const volume = this.volumes.get(name);

            if (!volume) {
                throw new NotFoundError('Volume not found.');
            }

            if (
                volume.references.size > 0 &&
                !options.force
            ) {
                throw new PolicyError(
                    `Volume is used by: ${[...volume.references].join(', ')}`
                );
            }

            if (volume.type !== MountType.BIND) {
                await fs.rm(volume.path, {
                    recursive: true,
                    force: false
                });
            }

            this.volumes.delete(name);

            this.emitEvent('volume.removed', { name });
        });
    }

    async storageReport() {
        const results = [];

        for (const name of this.volumes.keys()) {
            results.push(await this.inspectVolume(name));
        }

        return {
            volumeCount: results.length,
            totalBytes: results.reduce(
                (sum, volume) => sum + volume.sizeBytes,
                0
            ),
            volumes: results
        };
    }
}

async function main() {
    const root = await fs.mkdtemp(
        path.join(os.tmpdir(), 'docker-storage-')
    );

    const manager = await new StorageManager(root).initialize();

    manager.on('volume.created', event => {
        console.log('EVENT:', event.event, event.name);
    });

    manager.on('container.removed', event => {
        console.log('EVENT:', event.event, event.name);
    });

    try {
        await manager.createVolume('postgres_data', {
            labels: {
                environment: 'development',
                service: 'database'
            }
        });

        await manager.createContainer('postgres', [{
            type: MountType.NAMED,
            source: 'postgres_data',
            target: '/var/lib/postgresql/data'
        }]);

        await manager.startContainer('postgres');

        await manager.writeFile(
            'postgres',
            '/var/lib/postgresql/data/database.txt',
            'Persistent database records'
        );

        await manager.writeFile(
            'postgres',
            '/tmp/session.txt',
            'Temporary container data'
        );

        console.assert(
            await manager.readFile(
                'postgres',
                '/var/lib/postgresql/data/database.txt'
            ) === 'Persistent database records'
        );

        console.assert(
            await manager.readFile(
                'postgres',
                '/tmp/session.txt'
            ) === 'Temporary container data'
        );

        try {
            await manager.removeVolume('postgres_data');
            throw new Error('In-use volume removal should fail.');
        } catch (error) {
            if (!(error instanceof PolicyError)) throw error;
            console.log('In-use volume deletion correctly rejected.');
        }

        const backup = await manager.backupVolume('postgres_data');

        await manager.removeContainer('postgres');

        console.assert(
            (await manager.inspectVolume('postgres_data')).sizeBytes > 0
        );

        await manager.restoreVolume(backup, 'postgres_recovery');

        await manager.createContainer('recovery', [{
            type: MountType.NAMED,
            source: 'postgres_recovery',
            target: '/var/lib/postgresql/data'
        }]);

        await manager.startContainer('recovery');

        console.assert(
            await manager.readFile(
                'recovery',
                '/var/lib/postgresql/data/database.txt'
            ) === 'Persistent database records'
        );

        const hostDirectory = path.join(root, 'host-config');

        await fs.mkdir(hostDirectory);

        await fs.writeFile(
            path.join(hostDirectory, 'config.txt'),
            'Host-controlled configuration'
        );

        await manager.createBindMount(
            'application_config',
            hostDirectory,
            { readOnly: true }
        );

        await manager.createContainer('application', [{
            type: MountType.BIND,
            source: 'application_config',
            target: '/etc/application',
            readOnly: true
        }]);

        await manager.startContainer('application');

        console.assert(
            await manager.readFile(
                'application',
                '/etc/application/config.txt'
            ) === 'Host-controlled configuration'
        );

        try {
            await manager.writeFile(
                'application',
                '/etc/application/config.txt',
                'Unauthorized write'
            );

            throw new Error('Read-only mount should reject writes.');
        } catch (error) {
            if (!(error instanceof PolicyError)) throw error;
            console.log('Read-only mount correctly enforced.');
        }

        await manager.removeContainer('application');
        await manager.removeContainer('recovery');

        await manager.removeVolume('postgres_recovery');

        console.log(
            JSON.stringify(await manager.storageReport(), null, 2)
        );

        console.log('All storage lifecycle tests passed.');

    } finally {
        await fs.rm(root, {
            recursive: true,
            force: true
        });
    }
}

main().catch(error => {
    console.error('Storage operation failed:', error.message);
    process.exitCode = 1;
});
