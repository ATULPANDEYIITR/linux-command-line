'use strict';

/*
 * Cloud Scaling Architecture
 *
 * Models:
 * Client -> Load Balancer -> Auto Scaled Compute Pool
 *                         -> Health Checks
 *                         -> Scaling Policy
 *
 * The implementation deliberately separates request routing,
 * instance health, and scaling decisions.
 */

const InstanceState = Object.freeze({
  STARTING: 'starting',
  HEALTHY: 'healthy',
  UNHEALTHY: 'unhealthy',
  DRAINING: 'draining',
  TERMINATED: 'terminated'
});

const ScalingAction = Object.freeze({
  SCALE_OUT: 'scale_out',
  SCALE_IN: 'scale_in',
  HOLD: 'hold'
});

class ValidationError extends Error {}

class Instance {
  constructor(id, capacityRps) {
    if (!Number.isInteger(capacityRps) || capacityRps <= 0) {
      throw new ValidationError('Instance capacity must be positive');
    }

    this.id = id;
    this.capacityRps = capacityRps;
    this.state = InstanceState.STARTING;
    this.activeRequests = 0;
  }

  get availableCapacity() {
    if (this.state !== InstanceState.HEALTHY) {
      return 0;
    }

    return Math.max(0, this.capacityRps - this.activeRequests);
  }
}

class LoadBalancer {
  constructor(name, timeoutMs = 500) {
    if (!name) {
      throw new ValidationError('Load balancer name is required');
    }

    this.name = name;
    this.timeoutMs = timeoutMs;
    this.cursor = 0;
  }

  healthyInstances(instances) {
    return instances.filter(
      instance => instance.state === InstanceState.HEALTHY
    );
  }

  route(requests, instances) {
    if (!Number.isInteger(requests) || requests < 0) {
      throw new ValidationError('Requests must be a non-negative integer');
    }

    const healthy = this.healthyInstances(instances);

    if (healthy.length === 0) {
      throw new Error('Load balancer has no healthy targets');
    }

    const allocation = new Map(
      instances.map(instance => [instance.id, 0])
    );

    let remaining = requests;
    const start = this.cursor % healthy.length;

    while (remaining > 0) {
      let progress = false;

      for (let offset = 0; offset < healthy.length; offset += 1) {
        const instance = healthy[(start + offset) % healthy.length];
        const capacity = instance.availableCapacity;

        if (capacity <= 0) {
          continue;
        }

        const assigned = Math.min(capacity, remaining);
        instance.activeRequests += assigned;
        allocation.set(
          instance.id,
          allocation.get(instance.id) + assigned
        );

        remaining -= assigned;
        progress = true;

        if (remaining === 0) {
          break;
        }
      }

      if (!progress) {
        break;
      }
    }

    this.cursor = (start + 1) % healthy.length;

    return {
      allocation,
      served: requests - remaining,
      rejected: remaining
    };
  }
}

class AutoScaler {
  constructor({
    minInstances = 2,
    maxInstances = 8,
    scaleOutThreshold = 0.75,
    scaleInThreshold = 0.30,
    cooldownTicks = 2
  } = {}) {
    if (minInstances < 1 || maxInstances < minInstances) {
      throw new ValidationError('Invalid instance limits');
    }

    if (!(scaleInThreshold > 0 &&
          scaleInThreshold < scaleOutThreshold &&
          scaleOutThreshold <= 1)) {
      throw new ValidationError('Invalid scaling thresholds');
    }

    this.minInstances = minInstances;
    this.maxInstances = maxInstances;
    this.scaleOutThreshold = scaleOutThreshold;
    this.scaleInThreshold = scaleInThreshold;
    this.cooldownTicks = cooldownTicks;
    this.cooldownRemaining = 0;
  }

  evaluate(requestRate, capacity) {
    if (capacity <= 0) {
      return ScalingAction.SCALE_OUT;
    }

    if (this.cooldownRemaining > 0) {
      this.cooldownRemaining -= 1;
      return ScalingAction.HOLD;
    }

    const utilization = requestRate / capacity;

    if (utilization > this.scaleOutThreshold) {
      return ScalingAction.SCALE_OUT;
    }

    if (utilization < this.scaleInThreshold) {
      return ScalingAction.SCALE_IN;
    }

    return ScalingAction.HOLD;
  }

  startCooldown() {
    this.cooldownRemaining = this.cooldownTicks;
  }
}

class ScalingArchitecture {
  constructor(options = {}) {
    this.loadBalancer = new LoadBalancer(
      options.loadBalancerName ?? 'public-alb'
    );

    this.autoScaler = new AutoScaler(options);
    this.instances = [];
    this.nextId = 1;

    this.scaleTo(this.autoScaler.minInstances);
    this.activateStartingInstances();
  }

  activeInstances() {
    return this.instances.filter(
      instance => instance.state !== InstanceState.TERMINATED
    );
  }

  healthyInstances() {
    return this.loadBalancer.healthyInstances(
      this.activeInstances()
    );
  }

  totalCapacity() {
    return this.healthyInstances().reduce(
      (sum, instance) => sum + instance.capacityRps,
      0
    );
  }

  createInstance() {
    /*
     * In production this would invoke a VM, container, or
     * orchestration API. The simulation uses deterministic capacity.
     */
    const capacity = 100 + ((this.nextId * 17) % 31);
    const instance = new Instance(
      `compute-${String(this.nextId).padStart(2, '0')}`,
      capacity
    );

    this.nextId += 1;
    return instance;
  }

  activateStartingInstances() {
    for (const instance of this.instances) {
      if (instance.state === InstanceState.STARTING) {
        instance.state = InstanceState.HEALTHY;
      }
    }
  }

  scaleTo(desired) {
    desired = Math.max(
      this.autoScaler.minInstances,
      Math.min(this.autoScaler.maxInstances, desired)
    );

    const active = this.activeInstances();

    if (active.length < desired) {
      while (this.activeInstances().length < desired) {
        this.instances.push(this.createInstance());
      }

      this.activateStartingInstances();
      return;
    }

    if (active.length > desired) {
      const removable = active.filter(
        instance =>
          instance.state === InstanceState.HEALTHY &&
          instance.activeRequests === 0
      );

      const count = active.length - desired;

      for (const instance of removable.slice(0, count)) {
        instance.state = InstanceState.TERMINATED;
      }
    }
  }

  setInstanceHealth(id, healthy) {
    const instance = this.activeInstances().find(
      candidate => candidate.id === id
    );

    if (!instance) {
      throw new Error(`Unknown instance: ${id}`);
    }

    instance.state = healthy
      ? InstanceState.HEALTHY
      : InstanceState.UNHEALTHY;
  }

  processTraffic(requestRate) {
    if (!Number.isInteger(requestRate) || requestRate < 0) {
      throw new ValidationError('Traffic must be a non-negative integer');
    }

    for (const instance of this.activeInstances()) {
      instance.activeRequests = 0;
    }

    const action = this.autoScaler.evaluate(
      requestRate,
      this.totalCapacity()
    );

    if (action === ScalingAction.SCALE_OUT) {
      this.scaleTo(this.activeInstances().length + 1);
      this.autoScaler.startCooldown();
    } else if (action === ScalingAction.SCALE_IN) {
      this.scaleTo(this.activeInstances().length - 1);
      this.autoScaler.startCooldown();
    }

    let result;

    try {
      result = this.loadBalancer.route(
        requestRate,
        this.activeInstances()
      );
    } catch (error) {
      result = {
        allocation: new Map(),
        served: 0,
        rejected: requestRate,
        error: error.message
      };
    }

    for (const instance of this.activeInstances()) {
      instance.activeRequests = 0;
    }

    return {
      action,
      instanceCount: this.activeInstances().length,
      healthyCount: this.healthyInstances().length,
      capacity: this.totalCapacity(),
      served: result.served,
      rejected: result.rejected,
      allocation: Object.fromEntries(result.allocation ?? []),
      error: result.error ?? null
    };
  }
}

async function runEventDrivenSimulation() {
  const architecture = new ScalingArchitecture({
    minInstances: 2,
    maxInstances: 6,
    scaleOutThreshold: 0.75,
    scaleInThreshold: 0.30,
    cooldownTicks: 2
  });

  const traffic = [80, 120, 190, 260, 480, 620, 300, 140, 70];

  console.log('Cloud Scaling Architecture');
  console.log('='.repeat(72));

  for (let tick = 0; tick < traffic.length; tick += 1) {
    if (tick === 5 && architecture.healthyInstances().length > 0) {
      architecture.setInstanceHealth(
        architecture.healthyInstances()[0].id,
        false
      );
    }

    const result = architecture.processTraffic(traffic[tick]);

    console.log(
      `Tick ${(tick + 1).toString().padStart(2, '0')} | ` +
      `requests=${traffic[tick].toString().padStart(3)} | ` +
      `action=${result.action.padEnd(9)} | ` +
      `instances=${result.instanceCount} | ` +
      `healthy=${result.healthyCount} | ` +
      `capacity=${result.capacity} | ` +
      `served=${result.served} | ` +
      `rejected=${result.rejected}`
    );

    if (tick === 6) {
      for (const instance of architecture.activeInstances()) {
        if (instance.state === InstanceState.UNHEALTHY) {
          instance.state = InstanceState.HEALTHY;
        }
      }
    }

    await new Promise(resolve => setTimeout(resolve, 10));
  }
}

function runAssertions() {
  const architecture = new ScalingArchitecture({
    minInstances: 2,
    maxInstances: 4
  });

  if (architecture.activeInstances().length !== 2) {
    throw new Error('Minimum capacity assertion failed');
  }

  const result = architecture.processTraffic(20);

  if (result.served !== 20 || result.rejected !== 0) {
    throw new Error('Normal traffic routing assertion failed');
  }

  architecture.setInstanceHealth('compute-01', false);

  if (architecture.healthyInstances().length !== 1) {
    throw new Error('Health isolation assertion failed');
  }

  let rejected = false;

  try {
    architecture.processTraffic(-1);
  } catch (error) {
    rejected = error instanceof ValidationError;
  }

  if (!rejected) {
    throw new Error('Input validation assertion failed');
  }
}

runAssertions();
runEventDrivenSimulation().catch(error => {
  console.error('Simulation failed:', error.message);
  process.exitCode = 1;
});
