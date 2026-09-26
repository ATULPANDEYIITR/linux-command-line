/*
 * TCP AND UDP: JAVASCRIPT NETWORKING STUDY FILE
 * ==============================================
 *
 * This file demonstrates:
 *
 * - TCP and UDP conceptual differences
 * - Node.js networking APIs
 * - TCP client/server communication
 * - TCP stream framing
 * - UDP datagram communication
 * - UDP message boundaries
 * - timeouts and error handling
 * - application-level reliability concepts
 * - performance and security considerations
 *
 * Runtime:
 *   Node.js 18+ recommended
 *
 * No external npm packages are required.
 */

"use strict";

const net = require("net");
const dgram = require("dgram");
const crypto = require("crypto");


// ============================================================================
// 1. BASIC CONCEPTS
// ============================================================================

function section(title) {
    console.log("\n" + "=".repeat(78));
    console.log(title);
    console.log("=".repeat(78));
}

function explainBasics() {
    section("1. TCP AND UDP FUNDAMENTALS");

    console.log(`
TCP:
  - Connection-oriented transport protocol.
  - Provides an ordered byte stream.
  - Uses acknowledgements and retransmission.
  - Provides flow and congestion control.
  - Does not preserve application message boundaries.

UDP:
  - Connectionless transport protocol.
  - Sends independent datagrams.
  - Preserves datagram boundaries.
  - Does not provide TCP-style reliability or ordering.
  - Can be useful for latency-sensitive and discovery-oriented traffic.

A network endpoint can be described conceptually as:

  IP address + transport protocol + port

Node.js exposes TCP through the "net" module and UDP through "dgram".
`);
}


// ============================================================================
// 2. TCP FRAMING
// ============================================================================

const MAX_FRAME_SIZE = 1024 * 1024;

/*
 * TCP provides a byte stream.
 *
 * If an application sends:
 *
 *     send("HELLO");
 *     send("WORLD");
 *
 * the receiver might observe:
 *
 *     "HELLOWORLD"
 *
 * or:
 *
 *     "HE"
 *     "LLOW"
 *     "ORLD"
 *
 * Therefore a protocol running over TCP needs framing.
 *
 * This example uses a 4-byte unsigned big-endian length prefix.
 */

function encodeFrame(payload) {
    const payloadBuffer = Buffer.isBuffer(payload)
        ? payload
        : Buffer.from(payload, "utf8");

    if (payloadBuffer.length > MAX_FRAME_SIZE) {
        throw new RangeError("Payload exceeds maximum frame size");
    }

    const header = Buffer.alloc(4);
    header.writeUInt32BE(payloadBuffer.length, 0);

    return Buffer.concat([header, payloadBuffer]);
}

class FrameDecoder {
    constructor(maxFrameSize = MAX_FRAME_SIZE) {
        this.maxFrameSize = maxFrameSize;
        this.buffer = Buffer.alloc(0);
    }

    push(chunk) {
        if (!Buffer.isBuffer(chunk)) {
            throw new TypeError("TCP data must be a Buffer");
        }

        this.buffer = Buffer.concat([this.buffer, chunk]);

        const messages = [];

        while (this.buffer.length >= 4) {
            const length = this.buffer.readUInt32BE(0);

            if (length > this.maxFrameSize) {
                throw new RangeError("Incoming frame exceeds configured limit");
            }

            const completeFrameLength = 4 + length;

            if (this.buffer.length < completeFrameLength) {
                break;
            }

            const payload = this.buffer.subarray(4, completeFrameLength);

            messages.push(payload);

            this.buffer = this.buffer.subarray(completeFrameLength);
        }

        return messages;
    }
}

function demonstrateFraming() {
    section("2. TCP STREAM FRAMING");

    const combined = Buffer.concat([
        encodeFrame("FIRST"),
        encodeFrame("SECOND"),
        encodeFrame("THIRD")
    ]);

    // Deliberately split the stream at arbitrary boundaries.
    const chunks = [
        combined.subarray(0, 2),
        combined.subarray(2, 8),
        combined.subarray(8, 13),
        combined.subarray(13)
    ];

    const decoder = new FrameDecoder();

    for (const chunk of chunks) {
        const messages = decoder.push(chunk);

        console.log(
            `Received ${chunk.length} bytes ->`,
            messages.map(message => message.toString("utf8"))
        );
    }

    console.log("Remaining buffered bytes:", decoder.buffer.length);
}


// ============================================================================
// 3. TCP SERVER
// ============================================================================

function startTcpServer() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();

        server.on("error", reject);

        server.on("connection", socket => {
            console.log(
                `TCP connection from ${socket.remoteAddress}:${socket.remotePort}`
            );

            socket.setTimeout(5000);

            const decoder = new FrameDecoder();

            socket.on("data", chunk => {
                try {
                    const messages = decoder.push(chunk);

                    for (const message of messages) {
                        console.log(
                            "TCP server received:",
                            message.toString("utf8")
                        );

                        const response = `TCP response: ${message.toString("utf8")}`;

                        socket.write(encodeFrame(response));
                    }
                } catch (error) {
                    console.error("TCP protocol error:", error.message);
                    socket.destroy();
                }
            });

            socket.on("timeout", () => {
                console.log("TCP connection timed out.");
                socket.end();
            });

            socket.on("error", error => {
                console.error("TCP socket error:", error.message);
            });

            socket.on("close", () => {
                console.log("TCP connection closed.");
            });
        });

        server.listen(0, "127.0.0.1", () => {
            const address = server.address();

            if (!address || typeof address === "string") {
                reject(new Error("Unable to determine TCP server address"));
                return;
            }

            resolve({ server, port: address.port });
        });
    });
}


// ============================================================================
// 4. TCP CLIENT
// ============================================================================

function tcpRequest(port, message) {
    return new Promise((resolve, reject) => {
        const socket = net.createConnection({
            host: "127.0.0.1",
            port
        });

        const decoder = new FrameDecoder();
        let completed = false;

        const timeout = setTimeout(() => {
            if (!completed) {
                completed = true;
                socket.destroy();
                reject(new Error("TCP request timed out"));
            }
        }, 5000);

        socket.on("connect", () => {
            socket.write(encodeFrame(message));
        });

        socket.on("data", chunk => {
            try {
                const messages = decoder.push(chunk);

                if (messages.length > 0 && !completed) {
                    completed = true;
                    clearTimeout(timeout);

                    resolve(messages[0].toString("utf8"));
                    socket.end();
                }
            } catch (error) {
                if (!completed) {
                    completed = true;
                    clearTimeout(timeout);
                    socket.destroy();
                    reject(error);
                }
            }
        });

        socket.on("error", error => {
            if (!completed) {
                completed = true;
                clearTimeout(timeout);
                reject(error);
            }
        });
    });
}


// ============================================================================
// 5. UDP SERVER
// ============================================================================

function startUdpServer() {
    return new Promise((resolve, reject) => {
        const server = dgram.createSocket("udp4");

        const timeout = setTimeout(() => {
            server.close();
            reject(new Error("UDP server startup timed out"));
        }, 3000);

        server.once("error", error => {
            clearTimeout(timeout);
            reject(error);
        });

        server.on("message", (message, remoteInfo) => {
            console.log(
                `UDP datagram from ${remoteInfo.address}:${remoteInfo.port}:`,
                message.toString("utf8")
            );

            const response = Buffer.from(
                `UDP response: ${message.toString("utf8")}`
            );

            server.send(
                response,
                remoteInfo.port,
                remoteInfo.address,
                error => {
                    if (error) {
                        console.error("UDP send error:", error.message);
                    }
                }
            );
        });

        server.bind(0, "127.0.0.1", () => {
            clearTimeout(timeout);

            const address = server.address();

            if (!address || typeof address === "string") {
                reject(new Error("Unable to determine UDP address"));
                return;
            }

            resolve({
                server,
                port: address.port
            });
        });
    });
}


// ============================================================================
// 6. UDP CLIENT
// ============================================================================

function udpRequest(port, message) {
    return new Promise((resolve, reject) => {
        const socket = dgram.createSocket("udp4");
        const payload = Buffer.from(message, "utf8");

        let finished = false;

        const finish = (callback, value) => {
            if (finished) {
                return;
            }

            finished = true;
            clearTimeout(timeout);
            socket.close();
            callback(value);
        };

        const timeout = setTimeout(() => {
            finish(reject, new Error("UDP request timed out"));
        }, 3000);

        socket.on("error", error => {
            finish(reject, error);
        });

        socket.on("message", messageBuffer => {
            finish(resolve, messageBuffer.toString("utf8"));
        });

        socket.send(payload, port, "127.0.0.1", error => {
            if (error) {
                finish(reject, error);
            }
        });
    });
}


// ============================================================================
// 7. UDP MESSAGE BOUNDARIES
// ============================================================================

async function demonstrateUdpMessageBoundaries() {
    section("7. UDP DATAGRAM BOUNDARIES");

    const server = dgram.createSocket("udp4");

    await new Promise((resolve, reject) => {
        server.once("error", reject);

        server.bind(0, "127.0.0.1", () => {
            resolve();
        });
    });

    const address = server.address();

    const received = [];

    server.on("message", message => {
        received.push(message.toString("utf8"));

        if (received.length === 2) {
            console.log("First datagram:", received[0]);
            console.log("Second datagram:", received[1]);
            server.close();
        }
    });

    const client = dgram.createSocket("udp4");

    try {
        await new Promise((resolve, reject) => {
            client.send(
                Buffer.from("ONE"),
                address.port,
                "127.0.0.1",
                error => {
                    if (error) {
                        reject(error);
                    } else {
                        resolve();
                    }
                }
            );
        });

        await new Promise((resolve, reject) => {
            client.send(
                Buffer.from("TWO"),
                address.port,
                "127.0.0.1",
                error => {
                    if (error) {
                        reject(error);
                    } else {
                        resolve();
                    }
                }
            );
        });

        await new Promise(resolve => {
            server.once("close", resolve);
        });
    } finally {
        client.close();
    }
}


// ============================================================================
// 8. APPLICATION-LEVEL UDP RELIABILITY
// ============================================================================

class ReliableUdpMessage {
    constructor(sequence, payload, timestamp = Date.now()) {
        if (!Number.isInteger(sequence) || sequence < 0) {
            throw new TypeError("Sequence must be a non-negative integer");
        }

        this.sequence = sequence;
        this.timestamp = timestamp;
        this.payload = Buffer.isBuffer(payload)
            ? payload
            : Buffer.from(payload, "utf8");
    }

    encode() {
        if (this.payload.length > 1200) {
            throw new RangeError("Payload exceeds safe demonstration limit");
        }

        const object = {
            sequence: this.sequence,
            timestamp: this.timestamp,
            payload: this.payload.toString("base64")
        };

        return Buffer.from(JSON.stringify(object), "utf8");
    }

    static decode(buffer) {
        let object;

        try {
            object = JSON.parse(buffer.toString("utf8"));
        } catch {
            throw new Error("Invalid JSON packet");
        }

        if (!Number.isInteger(object.sequence) || object.sequence < 0) {
            throw new Error("Invalid sequence number");
        }

        if (typeof object.timestamp !== "number") {
            throw new Error("Invalid timestamp");
        }

        if (typeof object.payload !== "string") {
            throw new Error("Invalid payload");
        }

        const payload = Buffer.from(object.payload, "base64");

        if (payload.length > 1200) {
            throw new Error("Payload exceeds limit");
        }

        return new ReliableUdpMessage(
            object.sequence,
            payload,
            object.timestamp
        );
    }
}

function demonstrateReliableUdpMessage() {
    section("8. APPLICATION-LEVEL UDP RELIABILITY");

    const packet = new ReliableUdpMessage(
        42,
        "Important telemetry"
    );

    const encoded = packet.encode();
    const decoded = ReliableUdpMessage.decode(encoded);

    console.log("Encoded size:", encoded.length);
    console.log("Sequence:", decoded.sequence);
    console.log("Payload:", decoded.payload.toString("utf8"));

    /*
     * A production reliability layer could add:
     *
     * - acknowledgements
     * - sequence tracking
     * - retransmission timers
     * - duplicate suppression
     * - congestion control
     * - authentication
     * - replay protection
     *
     * Recreating TCP completely at the application level is complex.
     */
}


// ============================================================================
// 9. RETRANSMISSION SIMULATION
// ============================================================================

function simulatePacketLoss(lossProbability, seed = 12345) {
    /*
     * A deterministic pseudo-random generator makes this demonstration
     * repeatable without external dependencies.
     */
    let state = seed >>> 0;

    function random() {
        state = (1664525 * state + 1013904223) >>> 0;
        return state / 0x100000000;
    }

    return random() < lossProbability;
}

function demonstrateRetransmission() {
    section("9. UDP RETRANSMISSION CONCEPT");

    const maxAttempts = 5;
    const lossProbability = 0.35;

    let delivered = false;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const lost = simulatePacketLoss(
            lossProbability,
            100 + attempt
        );

        if (lost) {
            console.log(`Attempt ${attempt}: packet lost`);
        } else {
            console.log(`Attempt ${attempt}: packet delivered`);
            delivered = true;
            break;
        }
    }

    console.log(
        delivered
            ? "Application-level retry succeeded."
            : "Application-level retry exhausted."
    );
}


// ============================================================================
// 10. COMPARISON
// ============================================================================

function compareTcpUdp() {
    section("10. TCP VERSUS UDP");

    const rows = [
        ["Connection setup", "TCP handshake", "No TCP-style handshake"],
        ["Data abstraction", "Ordered byte stream", "Independent datagrams"],
        ["Ordering", "Provided", "Not guaranteed"],
        ["Retransmission", "Provided", "Not provided"],
        ["Message boundaries", "Not preserved", "Preserved"],
        ["Flow control", "Provided", "Not provided"],
        ["Congestion control", "TCP mechanisms", "Application/protocol dependent"],
        ["Multicast", "Not normal TCP behavior", "Supported by UDP/IP"],
        ["Common uses", "HTTP, SSH, databases", "DNS, telemetry, real-time traffic"]
    ];

    console.table(
        rows.map(row => ({
            Property: row[0],
            TCP: row[1],
            UDP: row[2]
        }))
    );
}


// ============================================================================
// 11. SECURITY
// ============================================================================

function explainSecurity() {
    section("11. SECURITY CONSIDERATIONS");

    console.log(`
TCP and UDP are transport protocols, not complete security systems.

TCP does not automatically encrypt application data.
UDP does not automatically encrypt or authenticate datagrams.

Production applications should consider:

- encryption
- authentication
- integrity protection
- authorization
- replay protection
- input validation
- maximum packet/message sizes
- rate limiting
- resource limits
- logging and monitoring

TLS is commonly used with TCP-based protocols.

QUIC is an important modern example of a protocol built over UDP that
provides reliability, security, multiplexing, and congestion-control
features above the UDP layer.
`);
}


// ============================================================================
// 12. PERFORMANCE
// ============================================================================

function explainPerformance() {
    section("12. PERFORMANCE AND DESIGN CONSIDERATIONS");

    console.log(`
TCP performance depends on:

- RTT
- available bandwidth
- congestion window
- receive window
- packet loss
- retransmission
- buffering
- application processing rate

UDP avoids TCP connection setup and stream-level retransmission, but the
application may need to implement reliability and congestion behavior.

Neither transport should be selected solely because it appears to have
lower overhead.

The application's communication semantics should drive the decision.
`);
}


// ============================================================================
// 13. ERROR HANDLING
// ============================================================================

function demonstrateValidation() {
    section("13. VALIDATION AND ERROR HANDLING");

    try {
        const decoder = new FrameDecoder(100);

        // Header claims a 101-byte payload, exceeding the configured limit.
        const maliciousHeader = Buffer.alloc(4);
        maliciousHeader.writeUInt32BE(101, 0);

        decoder.push(maliciousHeader);
    } catch (error) {
        console.log("Correctly rejected oversized frame:", error.message);
    }

    try {
        ReliableUdpMessage.decode(
            Buffer.from('{"sequence":"invalid"}')
        );
    } catch (error) {
        console.log("Correctly rejected malformed UDP message:", error.message);
    }
}


// ============================================================================
// 14. MAIN
// ============================================================================

async function main() {
    section("TCP AND UDP JAVASCRIPT STUDY PROGRAM");

    explainBasics();
    demonstrateFraming();

    const tcp = await startTcpServer();

    try {
        const tcpResponse = await tcpRequest(
            tcp.port,
            "Hello from TCP client"
        );

        console.log("TCP client received:", tcpResponse);
    } finally {
        tcp.server.close();
    }

    const udp = await startUdpServer();

    try {
        const udpResponse = await udpRequest(
            udp.port,
            "Hello from UDP client"
        );

        console.log("UDP client received:", udpResponse);
    } finally {
        udp.server.close();
    }

    await demonstrateUdpMessageBoundaries();

    demonstrateReliableUdpMessage();
    demonstrateRetransmission();
    compareTcpUdp();
    explainSecurity();
    explainPerformance();
    demonstrateValidation();

    section("END OF JAVASCRIPT STUDY PROGRAM");
}

main().catch(error => {
    console.error("Program failed:", error);
    process.exitCode = 1;
});
