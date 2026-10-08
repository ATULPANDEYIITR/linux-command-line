'use strict';

/*
 * Data Center Physical Infrastructure Event Simulator
 *
 * This implementation emphasizes JavaScript's event-driven model.
 * It models a facility where rack equipment produces electrical load,
 * electrical load becomes heat, infrastructure components can fail,
 * and monitoring events trigger policy evaluation.
 *
 * Run with:
 *   node data-center-infrastructure.js
 */

const EventEmitter = require('node:events');

const EquipmentState = Object.freeze({
  ONLINE: 'online',
  OFFLINE: 'offline',
  MAINTENANCE: 'maintenance'
});

const FailureType = Object.freeze({
  POWER_A: 'power_a',
  POWER_B: 'power_b',
  COOLING: 'cooling',
  TEMPERATURE: 'temperature'
});

class Server {
  constructor({ id, name, rackUnits, watts, dualPower }) {
    if (!id || !name) {
      throw new Error('Server requires an id and name.');
    }
    if (!Number.isInteger(rackUnits) || rackUnits <= 0) {
      throw new Error('rackUnits must be a positive integer.');
    }
    if (!Number.isFinite(watts) || watts <= 0) {
      throw new Error('watts must be positive.');
    }

    this.id = id;
    this.name = name;
    this.rackUnits = rackUnits;
    this.watts = watts;
    this.dualPower = Boolean(dualPower);
    this.state = EquipmentState.ONLINE;
  }

  get heatKw() {
    // Electrical power consumed by IT equipment is modeled as heat load.
    return this.watts / 1000;
  }
}

class Rack {
  constructor(id, totalU = 42) {
    if (totalU <= 0) {
      throw new Error('Rack capacity must be positive.');
    }

    this.id = id;
    this.totalU = totalU;
    this.servers = [];
    this.power = {
      A: { capacityKw: 10, loadKw: 0, online: true },
      B: { capacityKw: 10, loadKw: 0, online: true }
    };
  }

  get usedU() {
    return this.servers
      .filter(server => server.state !== EquipmentState.OFFLINE)
      .reduce((total, server) => total + server.rackUnits, 0);
  }

  get freeU() {
    return this.totalU - this.usedU;
  }

  install(server) {
    if (server.rackUnits > this.freeU) {
      throw new Error(
        `${this.id} has ${this.freeU}U free; ${server.name} needs ${server.rackUnits}U.`
      );
    }

    const loadKw = server.watts / 1000;

    if (server.dualPower) {
      const halfLoad = loadKw / 2;

      if (!this.power.A.online || !this.power.B.online) {
        throw new Error(
          `${server.id} requires both power paths during installation.`
        );
      }

      if (this.power.A.loadKw + halfLoad > this.power.A.capacityKw) {
        throw new Error(`${this.id} feed A would exceed capacity.`);
      }

      if (this.power.B.loadKw + halfLoad > this.power.B.capacityKw) {
        throw new Error(`${this.id} feed B would exceed capacity.`);
      }

      this.power.A.loadKw += halfLoad;
      this.power.B.loadKw += halfLoad;
    } else {
      if (this.power.A.loadKw + loadKw > this.power.A.capacityKw) {
        throw new Error(`${this.id} feed A would exceed capacity.`);
      }

      this.power.A.loadKw += loadKw;
    }

    this.servers.push(server);
  }

  totalITLoadKw() {
    return this.servers
      .filter(server => server.state !== EquipmentState.OFFLINE)
      .reduce((sum, server) => sum + server.watts / 1000, 0);
  }

  failPowerFeed(feed) {
    if (!this.power[feed]) {
      throw new Error(`Unknown power feed: ${feed}`);
    }

    this.power[feed].online = false;

    const affected = [];

    for (const server of this.servers) {
      if (server.state === EquipmentState.OFFLINE) {
        continue;
      }

      if (server.dualPower) {
        // Dual-corded equipment can remain operational because its other
        // power path is assumed to remain available.
        continue;
      }

      if (feed === 'A') {
        server.state = EquipmentState.OFFLINE;
        affected.push(server.id);
      }
    }

    return affected;
  }

  restorePowerFeed(feed) {
    if (!this.power[feed]) {
      throw new Error(`Unknown power feed: ${feed}`);
    }

    this.power[feed].online = true;

    // A real device may require a technician or automatic reboot. The
    // simulator uses a simple recovery policy for demonstration.
    for (const server of this.servers) {
      if (server.state === EquipmentState.OFFLINE) {
        server.state = EquipmentState.ONLINE;
      }
    }
  }
}

class CoolingUnit {
  constructor(id, capacityKw) {
    this.id = id;
    this.capacityKw = capacityKw;
    this.online = true;
  }
}

class DataCenter extends EventEmitter {
  constructor(name) {
    super();
    this.name = name;
    this.racks = new Map();
    this.coolingUnits = new Map();
    this.ambientTemperatureC = 22;
    this.maximumTemperatureC = 27;

    // EventEmitter is useful here because monitoring systems commonly react
    // to asynchronous facility events rather than repeatedly polling state.
    this.on('failure', event => this.handleFailure(event));
    this.on('temperatureAlert', event => {
      console.log(
        `[ALERT] Temperature ${event.temperatureC.toFixed(1)}°C exceeds ` +
        `${this.maximumTemperatureC}°C in ${this.name}.`
      );
    });
  }

  addRack(rack) {
    if (this.racks.has(rack.id)) {
      throw new Error(`Rack ${rack.id} already exists.`);
    }
    this.racks.set(rack.id, rack);
  }

  addCoolingUnit(unit) {
    if (this.coolingUnits.has(unit.id)) {
      throw new Error(`Cooling unit ${unit.id} already exists.`);
    }
    this.coolingUnits.set(unit.id, unit);
  }

  get totalITLoadKw() {
    let load = 0;
    for (const rack of this.racks.values()) {
      load += rack.totalITLoadKw();
    }
    return load;
  }

  get coolingCapacityKw() {
    let capacity = 0;
    for (const unit of this.coolingUnits.values()) {
      if (unit.online) {
        capacity += unit.capacityKw;
      }
    }
    return capacity;
  }

  coolingStatus() {
    const heat = this.totalITLoadKw;
    const capacity = this.coolingCapacityKw;

    return {
      heatKw: heat,
      capacityKw: capacity,
      marginKw: capacity - heat,
      sufficient: capacity >= heat,
      temperatureSafe: this.ambientTemperatureC <= this.maximumTemperatureC
    };
  }

  hasNPlusOneCooling() {
    const online = [...this.coolingUnits.values()].filter(unit => unit.online);

    if (online.length < 2) {
      return false;
    }

    const total = online.reduce((sum, unit) => sum + unit.capacityKw, 0);
    const largest = Math.max(...online.map(unit => unit.capacityKw));

    return total - largest >= this.totalITLoadKw;
  }

  setTemperature(temperatureC) {
    if (!Number.isFinite(temperatureC)) {
      throw new Error('Temperature must be numeric.');
    }

    this.ambientTemperatureC = temperatureC;

    if (temperatureC > this.maximumTemperatureC) {
      this.emit('temperatureAlert', { temperatureC });
    }
  }

  fail(componentType, componentId) {
    this.emit('failure', {
      type: componentType,
      componentId
    });
  }

  handleFailure(event) {
    if (event.type === FailureType.COOLING) {
      const unit = this.coolingUnits.get(event.componentId);

      if (!unit) {
        console.log(`[ERROR] Cooling unit ${event.componentId} not found.`);
        return;
      }

      unit.online = false;
      console.log(`[EVENT] ${unit.id} is offline.`);
      this.evaluateCooling();
      return;
    }

    if (
      event.type === FailureType.POWER_A ||
      event.type === FailureType.POWER_B
    ) {
      const rack = this.racks.get(event.componentId);

      if (!rack) {
        console.log(`[ERROR] Rack ${event.componentId} not found.`);
        return;
      }

      const feed = event.type === FailureType.POWER_A ? 'A' : 'B';
      const affected = rack.failPowerFeed(feed);

      console.log(
        `[EVENT] Rack ${rack.id} feed ${feed} failed; ` +
        `single-corded equipment affected: ${affected.join(', ') || 'none'}`
      );
    }
  }

  evaluateCooling() {
    const status = this.coolingStatus();

    console.log(
      `Cooling: ${status.heatKw.toFixed(2)} kW heat / ` +
      `${status.capacityKw.toFixed(2)} kW capacity / ` +
      `${status.marginKw.toFixed(2)} kW margin`
    );

    console.log(
      `N+1 cooling: ${this.hasNPlusOneCooling() ? 'PASS' : 'FAIL'}`
    );

    if (!status.sufficient) {
      console.log('[CRITICAL] Cooling capacity is below IT heat load.');
    }
  }

  report() {
    console.log(`\nDATA CENTER: ${this.name}`);
    console.log(`IT load: ${this.totalITLoadKw.toFixed(2)} kW`);
    console.log(`Cooling capacity: ${this.coolingCapacityKw.toFixed(2)} kW`);
    console.log(`Ambient temperature: ${this.ambientTemperatureC.toFixed(1)}°C`);

    for (const rack of this.racks.values()) {
      console.log(
        `Rack ${rack.id}: ${rack.usedU}/${rack.totalU}U, ` +
        `A=${rack.power.A.loadKw.toFixed(2)} kW ` +
        `B=${rack.power.B.loadKw.toFixed(2)} kW`
      );

      for (const server of rack.servers) {
        console.log(
          `  ${server.id}: ${server.state}, ` +
          `${server.watts} W, dual-power=${server.dualPower}`
        );
      }
    }
  }
}

function createFacility() {
  const dc = new DataCenter('Enterprise Compute Hall');

  const rackA01 = new Rack('A01');
  const rackA02 = new Rack('A02');
  const rackB01 = new Rack('B01');

  rackA01.install(new Server({
    id: 'SRV-101',
    name: 'Virtualization Host',
    rackUnits: 2,
    watts: 900,
    dualPower: true
  }));

  rackA01.install(new Server({
    id: 'SRV-102',
    name: 'Database Host',
    rackUnits: 2,
    watts: 750,
    dualPower: true
  }));

  rackA01.install(new Server({
    id: 'SRV-103',
    name: 'Facilities Gateway',
    rackUnits: 1,
    watts: 250,
    dualPower: false
  }));

  rackA02.install(new Server({
    id: 'SRV-201',
    name: 'Storage Controller',
    rackUnits: 2,
    watts: 700,
    dualPower: true
  }));

  rackB01.install(new Server({
    id: 'SRV-301',
    name: 'High Density Compute Node',
    rackUnits: 4,
    watts: 1400,
    dualPower: true
  }));

  dc.addRack(rackA01);
  dc.addRack(rackA02);
  dc.addRack(rackB01);

  dc.addCoolingUnit(new CoolingUnit('CRAC-01', 8));
  dc.addCoolingUnit(new CoolingUnit('CRAC-02', 8));
  dc.addCoolingUnit(new CoolingUnit('CRAC-03', 8));

  return dc;
}

async function runMonitoringCycle(dc) {
  // Promise-based scheduling models the asynchronous nature of environmental
  // monitoring and control systems without requiring external dependencies.
  await new Promise(resolve => setTimeout(resolve, 100));

  const status = dc.coolingStatus();

  console.log('\nMONITORING CYCLE');
  console.log(JSON.stringify(status, null, 2));

  if (!status.sufficient || !status.temperatureSafe) {
    console.log('[ACTION] Facility operator attention required.');
  } else {
    console.log('[ACTION] Environmental conditions acceptable.');
  }
}

async function main() {
  const dc = createFacility();

  dc.report();
  dc.evaluateCooling();

  await runMonitoringCycle(dc);

  console.log('\nSIMULATING COOLING FAILURE');
  dc.fail(FailureType.COOLING, 'CRAC-01');

  await runMonitoringCycle(dc);

  console.log('\nSIMULATING POWER-A FAILURE');
  dc.fail(FailureType.POWER_A, 'A01');

  dc.report();

  console.log('\nSIMULATING HIGH TEMPERATURE');
  dc.setTemperature(29);

  console.log('\nRESTORING COOLING AND POWER');
  dc.coolingUnits.get('CRAC-01').online = true;
  dc.racks.get('A01').restorePowerFeed('A');

  dc.setTemperature(22);
  dc.evaluateCooling();
  dc.report();
}

main().catch(error => {
  console.error(`[FATAL] ${error.message}`);
  process.exitCode = 1;
});
