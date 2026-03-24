import random

def generate_mac():
    return ':'.join(format(random.randint(0,255), '02X') for _ in range(6))

# Physical Layer
class Signal:
    def __init__(self, message, sender, destination=None, is_bits=False):
        self.message = message
        self.sender = sender
        self.destination = destination
        self.corrupted = False

        if is_bits:
            self.bits = message   
        else:
            self.bits = self._encode()

    #encode message(to bits)
    def _encode(self):
        return ' '.join(format(ord(c), '08b') for c in self.message)
    
    def corrupt(self, other_bits):
        b1 = self.bits.replace(' ','')
        b2 = other_bits.replace(' ','')

        maxlen = max(len(b1),len(b2))
        b1 = b1.zfill(maxlen)
        b2 = b2.zfill(maxlen)

        corrupted = ''.join(str(int(a) ^ int(b)) for a, b in zip(b1, b2))
        self.bits = ' '.join(corrupted[i:i+8] for i in range(0, len(corrupted), 8))
        self.corrupted = True

    def __str__(self):
        if self.corrupted:
            status = " [CORRUPTED]"
        else:
            status = " "

        if self.destination:
            dest = self.destination
        else:
            dest = " BROADCAST"

        return (
            f"From : {self.sender}\n"
            f"To   : {dest}\n"
            f"Message  : {self.message}\n"
            f"Bits : {self.bits}{status}\n"    
        )

# Data Link Layer
class Frame:
    def __init__(self, src_mac, dst_mac, data, seq_num=0):
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.data = data
        self.seq_num = seq_num
        self.bits = self._to_bits()
        self.hamming_blocks = self._apply_hamming()
        self.corrupted = False
        self.error_position = None
    
    def _to_bits(self):
        return ' '.join(format(ord(c), '08b') for c in self.data)
    
    def _apply_hamming(self):
        # apply hamming per byte (8 bits)
        bytes_list = [format(ord(c), '08b') for c in self.data]
        blocks = []
        for byte in bytes_list:
            blocks.append(self._hamming_encode(byte))
        return blocks
    
    def _hamming_encode(self, byte):

        d = [int(b) for b in byte]

        c = [0] * 12
        data_positions = [3, 5, 6, 7, 9, 10, 11, 12]
        for i, pos in enumerate(data_positions):
            c[pos - 1] = d[i]

        # calculate parity bits
        c[0] = c[2]^c[4]^c[6]^c[8]^c[10]        # P1: positions 1,3,5,7,9,11
        c[1] = c[2]^c[5]^c[6]^c[9]^c[10]        # P2: positions 2,3,6,7,10,11
        c[3] = c[4]^c[5]^c[6]^c[11]             # P4: positions 4,5,6,7,12
        c[7] = c[8]^c[9]^c[10]^c[11]            # P8: positions 8,9,10,11,12

        return c
    
    def verify_hamming(self):
        # recheck all blocks for errors
        errors = []
        for i, block in enumerate(self.hamming_blocks):
            pos = self._check_parity(block)
            if pos != 0:
                errors.append((i, pos))
        return errors
    
    def _check_parity(self, c):
        # recalculate syndrome bits
        p1 = c[0]^c[2]^c[4]^c[6]^c[8]^c[10]
        p2 = c[1]^c[2]^c[5]^c[6]^c[9]^c[10]
        p4 = c[3]^c[4]^c[5]^c[6]^c[11]
        p8 = c[7]^c[8]^c[9]^c[10]^c[11]
        # syndrome = error position (0 means no error)
        return p1 + 2*p2 + 4*p4 + 8*p8
    
    def correct_errors(self):
        errors = self.verify_hamming()
        if not errors:
            print(f"   No errors detected in frame (seq={self.seq_num})")
            return
        for block_idx, bit_pos in errors:
            print(f"   Error detected in block {block_idx+1} at bit position {bit_pos} — correcting...")
            # flip the bit
            self.hamming_blocks[block_idx][bit_pos - 1] ^= 1
        print(f"   All errors corrected!")

    def to_bits(self):
        raw = f"{self.src_mac}|{self.dst_mac}|{self.seq_num}|{self.data}"
        return ' '.join(format(ord(c), '08b') for c in raw)

    @classmethod
    def from_bits(cls, bits):
        bit_list = bits.replace(' ', '')
        chars = []
        for i in range(0, len(bit_list), 8):
            byte = bit_list[i:i+8]
            if len(byte) == 8:
                try:
                    chars.append(chr(int(byte, 2)))
                except:
                    return None
        raw = ''.join(chars)
        try:
            parts = raw.split('|')
            return cls(parts[0], parts[1], parts[3], int(parts[2]))
        except:
            print("[PHY→DLL] Failed to reconstruct frame — signal corrupted")
            return None
    def __str__(self):
        status = "[CORRUPTED]" if self.corrupted else ""
        return (
            f"  Src MAC  : {self.src_mac}\n"
            f"  Dst MAC  : {self.dst_mac}\n"
            f"  Seq No   : {self.seq_num}\n"
            f"  Data     : {self.data}\n"
            f"  Bits     : {self.bits} {status}\n"
            f"  Hamming  : {[''.join(map(str,b)) for b in self.hamming_blocks]}\n"
        )
    
class EndDevice:
    def __init__(self, name,):
        self.name = name
        self.port = None
        self.mac = generate_mac()

    def connect(self, cable):
        if self.port is not None:
            print(f"{self.name} already connected.")
            return
        self.port = cable
        cable.connect(self)

    def send(self, message, destination=None):
        if self.port is None:
            print(f"{self.name} is not connected to any cable")
            return
        signal = Signal(message, sender=self.name, destination=destination)
        print(f"{self.name} wants to send to {destination or 'BROADCAST'}")
        print(f"Signal Generated:")
        print(signal)
        self.port.transmit(signal, sender=self)

    def transmit(self, signal, sender):
        self.receive(signal)

    def receive(self, signal):
        if signal.corrupted:
            print(f"{self.name} received a CORRUPTED signal, collision occurred!")
            return
        if signal.destination and signal.destination != self.name:
            print(f"{self.name} dropping signal (not intended for it)")
            return
        print(f"{self.name} recevied:")
        print(signal)

    def dll_send(self, message, destination_mac, seq_num=0):
        if self.port is None:
            print(f"[DLL] {self.name} is not connected!")
            return
        # DLL creates frame
        print(f"\n[DLL] Creating frame...")
        frame = Frame(self.mac, destination_mac, message, seq_num)
        print(frame)

        # DLL passes frame DOWN to PHY
        signal = self.phy_send(frame)

        # PHY transmits signal through port
        self.port.transmit(signal, frame, sender=self)

    def dll_receive(self, frame):
        if frame.dst_mac != self.mac:
            print(f" {self.name} dropping frame (not intended for it)")
            return
        # if GBN is active, route to gbn_receive
        if hasattr(self, 'expected_seq'):
            self.gbn_receive(frame)
        else:
            print(f"\n {self.name} received frame:")
            print(frame)
            print(f" {self.name} accepted frame — Data: '{frame.data}'")

    def gbn_send(self, messages, destination_mac, window_size=4, drop_prob=0.05):
        print(f"\n {self.name} starting Go-Back-N transmission")
        print(f" Window size: {window_size} | Drop probability: {drop_prob}")
        print(f" Total frames to send: {len(messages)}")

        self.window_size = window_size
        self.send_base = 0
        self.next_seq = 0
        self.unacked = {}  # seq_num → frame
        self.dropped_frames = set()

        total = len(messages)

        while self.send_base < total:
            # send all frames within window
            while self.next_seq < self.send_base + window_size and self.next_seq < total:
                frame = Frame(self.mac, destination_mac, messages[self.next_seq], self.next_seq)
                self.unacked[self.next_seq] = frame

                # simulate random drop
                dropped = random.random() < drop_prob
                if dropped:
                    print(f"\n Frame {self.next_seq} DROPPED (simulated loss)!")
                    self.dropped_frames.add(self.next_seq)
                else:
                    print(f"\n Sending frame {self.next_seq}: '{messages[self.next_seq]}'")
                    print(frame)
                    signal = self.phy_send(frame)
                    self.port.transmit(signal, frame, sender=self)

                self.next_seq += 1

            # simulate ACK from receiver
            # check which frames were actually received
            acked = self._wait_for_ack(total)

            if acked == self.send_base:
                # no new ACK — timeout, go back
                print(f"\n TIMEOUT! No ACK for frame {self.send_base}")
                print(f" Going back to frame {self.send_base} — resending window...")
                self.next_seq = self.send_base
            else:
                print(f"\n ACK received for frames up to {acked - 1}")
                self.send_base = acked

        print(f"\n All frames acknowledged — transmission complete!")

    def phy_send(self, frame):

        print(f"\n[PHY] Received frame from DLL layer")
        bits = frame.to_bits()
        signal = Signal(bits, sender=self.name, destination=frame.dst_mac, is_bits=True)
        print(f"[PHY] Frame converted to signal")
        print(f"[PHY] Bits: {signal.bits[:40]}...")
        return signal

    def phy_receive(self, signal):

        print(f"\n[PHY] Signal received — converting to frame for DLL layer")
        frame = Frame.from_bits(signal.bits)
        if frame is None:
            print("[PHY] Discarding corrupted frame")
            return None
        if frame:
            print(f"[PHY] Bits reconstructed into frame — passing to DLL layer")
            return frame
        else:
            print(f"[PHY] Signal too corrupted — could not reconstruct frame")
            return None
        
    def _wait_for_ack(self, total):
        for seq in range(self.send_base, min(self.send_base + self.window_size, total)):
            if seq in self.dropped_frames:
                print(f"\n[GBN] Receiver sending ACK {seq} (waiting for frame {seq})")
                return seq
        next_expected = min(self.send_base + self.window_size, total)
        print(f"\n[GBN] Receiver sending ACK {next_expected} (frames up to {next_expected-1} received ✓)")
        self.dropped_frames = set()   # clear after window slides
        return next_expected

    def gbn_receive(self, frame):
        if not hasattr(self, 'expected_seq'):
            self.expected_seq = 0

        print(f"\n[GBN] {self.name} received frame {frame.seq_num}: '{frame.data}'")

        if frame.seq_num == self.expected_seq:
            print(f"[GBN] Frame {frame.seq_num} accepted ✓")
            self.expected_seq += 1
            print(f"[GBN] {self.name} sending ACK {self.expected_seq} → expecting frame {self.expected_seq} next")
        else:
            print(f"[GBN] Frame {frame.seq_num} DISCARDED — expected frame {self.expected_seq}")
            print(f"[GBN] {self.name} sending ACK {self.expected_seq} → requesting retransmit from {self.expected_seq}")
    
class Hub:
    def __init__(self, name, num_ports):
        self.name = name
        self.num_ports = num_ports
        self.ports=[]

    def connect(self, device):
        if len(self.ports) >= self.num_ports:
            print(f"{self.name} is full! Cannot connect {device.name}")
            return
        self.ports.append(device)
        print(f"{self.name} connected to {device.name}")

    def transmit(self, signal, sender):
        print(f"{self.name} recevied signal from {signal.sender}")

        active = [d for d in self.ports if d != sender and getattr(d, '_transmitting', False)]

        if active:
            print(f"COLLISION DETECTED on {self.name}! ")
            print(f"Simultaneous transmission by: {signal.sender} and {', '.join(d.name for d in active)}")
            for d in active:
                signal.corrupt(d._current_signal.bits)

            print(f"Flooding CORRUPTED signal to all ports...")
            for device in self.ports:
                if device != sender:
                    device.receive(signal)
        else:
            recipients = [d for d in self.ports if d != sender]
            print(f"{self.name} flooding to: {', '.join(d.name for d in recipients)}")
            for device in recipients:
                device.receive(signal)

class Switch:
    def __init__(self, name, num_ports):
        self.name = name
        self.num_ports = num_ports
        self.ports = []
        self.mac_table = {}
        self.channel_busy = False

    def connect(self, device):
        if len(self.ports) >= self.num_ports:
            print(f" {self.name} is full! Cannot connect {device.name}")
            return
        self.ports.append(device)
        print(f" {device.name} (MAC: {device.mac}) connected to {self.name}")

    def transmit(self, signal, frame, sender):
        print(f"\n[DLL] {self.name} received signal from {sender.name}")

        # switch passes signal UP to PHY to reconstruct frame
        received_frame = sender.phy_receive(signal)
        if not received_frame:
            return

        # now DLL layer processes the frame
        # address learning
        if received_frame.src_mac not in self.mac_table:
            self.mac_table[received_frame.src_mac] = sender
            print(f"[DLL] {self.name} learned: {received_frame.src_mac} → {sender.name}")

        # error checking
        errors = received_frame.verify_hamming()
        if errors:
            print(f"[DLL] Errors found — correcting...")
            received_frame.correct_errors()
        else:
            print(f"[DLL] Hamming check passed — no errors")

        # forward or flood
        if received_frame.dst_mac in self.mac_table:
            destination = self.mac_table[received_frame.dst_mac]
            print(f"[DLL] Forwarding to {destination.name}")
            # pass signal DOWN to destination's PHY
            dest_frame = destination.phy_receive(signal)
            if dest_frame:
                destination.dll_receive(dest_frame)
        else:
            recipients = [d for d in self.ports if d != sender]
            print(f"[DLL] Destination unknown — flooding to: {', '.join(d.name for d in recipients)}")
            for device in recipients:
                dest_frame = device.phy_receive(signal)
                if dest_frame:
                    device.dll_receive(dest_frame)

    def show_mac_table(self):
        print(f"\n {self.name} MAC Table:")
        if not self.mac_table:
            print("  (empty)")
            return
        print(f"  {'MAC Address':<20} {'Device'}")
        print(f"  {'-'*30}")
        for mac, device in self.mac_table.items():
            print(f"  {mac:<20} {device.name}")
    def csma_cd_transmit(self, frame, sender):
        print(f"\n[CSMA/CD] {sender.name} wants to transmit...")

        # step 1 — sense channel
        if self.channel_busy:
            print(f"[CSMA/CD] Channel is BUSY — {sender.name} waiting...")
            # keep checking until free
            attempts = 0
            while self.channel_busy:
                attempts += 1
                if attempts > 5:
                    print(f"[CSMA/CD] {sender.name} giving up after too many attempts!")
                    return
            print(f"[CSMA/CD] Channel is FREE — {sender.name} proceeding...")

        # step 2 — mark channel busy
        self.channel_busy = True
        print(f"[CSMA/CD] Channel is FREE — {sender.name} starting transmission...")

        # step 3 — check for simultaneous transmission (collision)
        active_senders = getattr(self, '_active_senders', [])
        if active_senders:
            print(f"[CSMA/CD] *** COLLISION DETECTED! ***")
            print(f"[CSMA/CD] {sender.name} collided with {', '.join(s.name for s in active_senders)}")
            print(f"[CSMA/CD] Sending JAM signal to all devices...")
            for device in self.ports:
                print(f"[CSMA/CD] JAM → {device.name}")
            # backoff
            backoff = random.randint(1, 5)
            print(f"[CSMA/CD] {sender.name} backing off for {backoff} slot(s)...")
            self.channel_busy = False
            return

        # step 4 — no collision, proceed normally
        self._active_senders = [sender]
        signal = sender.phy_send(frame)
        self.transmit(signal, frame, sender)
        self._active_senders = []
        self.channel_busy = False
        print(f"[CSMA/CD] Transmission complete — channel FREE")

    def simulate_csma_collision(self, sender1, frame1, sender2, frame2):
        print(f"\n[CSMA/CD] {sender1.name} and {sender2.name} transmitting simultaneously!")
        self._active_senders = [sender1, sender2]
        self.channel_busy = True

        print(f"[CSMA/CD] *** COLLISION DETECTED! ***")
        print(f"[CSMA/CD] Sending JAM signal to all devices...")
        for device in self.ports:
            print(f"[CSMA/CD] JAM → {device.name}")

        backoff1 = random.randint(1, 5)
        backoff2 = random.randint(1, 5)
        print(f"[CSMA/CD] {sender1.name} backing off for {backoff1} slot(s)...")
        print(f"[CSMA/CD] {sender2.name} backing off for {backoff2} slot(s)...")

        self._active_senders = []
        self.channel_busy = False
        print(f"[CSMA/CD] Channel FREE — devices will retry...")

class Bridge:
    def __init__(self, name):
        self.name = name
        self.segment1 = []    # devices on left side
        self.segment2 = []    # devices on right side
        self.mac_table = {}   # MAC → segment number (1 or 2)

    def connect_segment(self, segment_num, devices):
        if segment_num == 1:
            self.segment1 = devices
            for d in devices:
                print(f"[DLL] {d.name} added to {self.name} Segment 1")
        elif segment_num == 2:
            self.segment2 = devices
            for d in devices:
                print(f"[DLL] {d.name} added to {self.name} Segment 2")
        else:
            print(f"[DLL] Bridge only has 2 segments!")

    def transmit(self, signal, frame, sender):
        print(f"\n[DLL] {self.name} received signal from {sender.name}")
        
        # reconstruct frame from signal
        received_frame = sender.phy_receive(signal)
        if not received_frame:
            return
        frame = received_frame

        # step 1 — learn source MAC
        if frame.src_mac not in self.mac_table:
            seg = 1 if sender in self.segment1 else 2
            self.mac_table[frame.src_mac] = seg
            print(f"[DLL] {self.name} learned: {frame.src_mac} → Segment {seg}")

        # step 2 — find which segment sender is on
        sender_seg = 1 if sender in self.segment1 else 2

        # step 3 — find destination segment
        if frame.dst_mac in self.mac_table:
            dst_seg = self.mac_table[frame.dst_mac]

            if dst_seg == sender_seg:
                # same segment — filter/block
                print(f"[DLL] {self.name} FILTERING frame — source and destination on same segment!")
                return
            else:
                # different segment — forward
                print(f"[DLL] {self.name} FORWARDING frame to Segment {dst_seg}")
                dst_devices = self.segment2 if dst_seg == 2 else self.segment1
                for device in dst_devices:
                    if device.mac == frame.dst_mac:
                        device.dll_receive(frame)
                        return
        else:
            # unknown destination — flood to other segment only
            other_seg = self.segment2 if sender_seg == 1 else self.segment1
            print(f"[DLL] {self.name} destination unknown — flooding to other segment...")
            for device in other_seg:
                device.dll_receive(frame)

    def show_mac_table(self):
        print(f"\n[DLL] {self.name} MAC Table:")
        if not self.mac_table:
            print("  (empty)")
            return
        print(f"  {'MAC Address':<20} {'Segment'}")
        print(f"  {'-'*30}")
        for mac, seg in self.mac_table.items():
            print(f"  {mac:<20} Segment {seg}")

class Topology:
    def __init__(self, name):
        self.name = name
        self.devices = {}
        self.hubs = {}
        self.switches = {} 
        self.bridges = {}
    
    def add_device(self, name):
        if name in self.devices:
            print(f"Device {name} already exists!")
            return
        self.devices[name] = EndDevice(name)
        print(f"EndDevice '{name}' created")
    
    def add_hub(self, name, num_ports):
        if name in self.hubs:
            print(f"Hub {name} already exists!")
            return
        self.hubs[name] = Hub(name, num_ports)
        print(f"Hub '{name}' created with {num_ports} ports")

    def connect(self, device_name, hub_name):
        if device_name not in self.devices:
            print(f" Device '{device_name}' not found!")
            return
        if hub_name not in self.hubs:
            print(f" Hub '{hub_name}' not found!")
            return
        device = self.devices[device_name]
        hub = self.hubs[hub_name]
        device.port = hub
        hub.connect(device)

    def simulate_collision(self, hub_name, sender1_name, msg1, sender2_name, msg2):
        if hub_name not in self.hubs:
            print(f" Hub '{hub_name}' not found!")
            return
        
        hub = self.hubs[hub_name]
        d1 = self.devices[sender1_name]
        d2 = self.devices[sender2_name]

        sig1 = Signal(msg1, sender=sender1_name)
        sig2 = Signal(msg2, sender=sender2_name)

        print(f"\n{sender1_name} and {sender2_name} transmitting simultaneously!")
        print(f"{sender1_name} signal: {sig1.bits}")
        print(f"{sender2_name} signal: {sig2.bits}")

        sig1.corrupt(sig2.bits)

        print(f"\n COLLISION DETECTED on {hub_name}! ")
        print(f"Corrupted signal: {sig1.bits}")
        print(f"\n{hub_name} flooding corrupted signal to all ports...")

        for device in hub.ports:
            if device != d1 and device != d2:
                device.receive(sig1)
            else:
                print(f"{device.name} (sender) — notified of collision")

    def build_star(self, hub_name, device_names, num_ports=None):
        if num_ports is None:
            num_ports = len(device_names)
        self.add_hub(hub_name, num_ports)

        for name in device_names:
            self.add_device(name)
            self.connect(name, hub_name)

        print(f"\nStar topology built — {len(device_names)} devices connected to {hub_name}")

    def build_point_to_point(self, device1_name, device2_name):
        self.add_device(device1_name)
        self.add_device(device2_name)
        self.connect_direct(device1_name, device2_name)

        print(f"\nPoint-to-point topology built — {device1_name} ↔ {device2_name}")

    def connect_direct(self, device1_name, device2_name):
        if device1_name not in self.devices or device2_name not in self.devices:
            print(f" One or both devices not found!")
            return
        d1 = self.devices[device1_name]
        d2 = self.devices[device2_name]
        d1.port = d2    
        d2.port = d1
        print(f" Direct connection: {device1_name} ↔ {device2_name}")

    def send(self, sender_name, message, destination=None):
        if sender_name not in self.devices:
            print(f" Sender '{sender_name}' not found!")
            return
        self.devices[sender_name].send(message, destination)

    def add_switch(self, name, num_ports):
        if name in self.__dict__.get('switches', {}):
            print(f"Switch {name} already exists!")
            return
        if not hasattr(self, 'switches'):
            self.switches = {}
        self.switches[name] = Switch(name, num_ports)
        print(f"[DLL] Switch '{name}' created with {num_ports} ports")

    def add_bridge(self, name):
        if not hasattr(self, 'bridges'):
            self.bridges = {}
        self.bridges[name] = Bridge(name)
        print(f"[DLL] Bridge '{name}' created")

    def connect_to_switch(self, device_name, switch_name):
        if not hasattr(self, 'switches'):
            self.switches = {}
        if device_name not in self.devices:
            print(f"Device '{device_name}' not found!")
            return
        if switch_name not in self.switches:
            print(f"Switch '{switch_name}' not found!")
            return
        device = self.devices[device_name]
        switch = self.switches[switch_name]
        device.port = switch
        switch.connect(device)

    def connect_bridge(self, bridge_name, seg1_devices, seg2_devices):
        if not hasattr(self, 'bridges'):
            self.bridges = {}
        if bridge_name not in self.bridges:
            print(f"Bridge '{bridge_name}' not found!")
            return
        bridge = self.bridges[bridge_name]
        seg1 = [self.devices[d] for d in seg1_devices if d in self.devices]
        seg2 = [self.devices[d] for d in seg2_devices if d in self.devices]
        bridge.connect_segment(1, seg1)
        bridge.connect_segment(2, seg2)
        # point devices to bridge
        for d in seg1 + seg2:
            d.port = bridge

    def build_switch_star(self, switch_name, device_names, num_ports=None):
        if num_ports is None:
            num_ports = len(device_names)
        self.add_switch(switch_name, num_ports)
        for name in device_names:
            self.add_device(name)
            self.connect_to_switch(name, switch_name)
        print(f"\n[DLL] Switch star topology built — {len(device_names)} devices connected to {switch_name}")

    def dll_send(self, sender_name, message, destination_name):
        if sender_name not in self.devices:
            print(f"Sender '{sender_name}' not found!")
            return
        if destination_name not in self.devices:
            print(f"Destination '{destination_name}' not found!")
            return
        sender = self.devices[sender_name]
        dst_mac = self.devices[destination_name].mac
        sender.dll_send(message, dst_mac)

    def gbn_send(self, sender_name, messages, destination_name, window_size=4, drop_prob=0.2):
        if sender_name not in self.devices:
            print(f"Sender '{sender_name}' not found!")
            return
        if destination_name not in self.devices:
            print(f"Destination '{destination_name}' not found!")
            return
        sender = self.devices[sender_name]
        dst_mac = self.devices[destination_name].mac
        sender.gbn_send(messages, dst_mac, window_size, drop_prob)

    def show_mac_table(self, device_name):
        if hasattr(self, 'switches') and device_name in self.switches:
            self.switches[device_name].show_mac_table()
        elif hasattr(self, 'bridges') and device_name in self.bridges:
            self.bridges[device_name].show_mac_table()
        else:
            print(f"Device '{device_name}' not found!")

    def show(self):
        print(f"\n{'='*40}")
        print(f"  Topology : {self.name}")
        print(f"  Devices  : {', '.join(self.devices.keys())}")
        print(f"  Hubs     : {', '.join(self.hubs.keys()) or 'None'}")
        print(f"  Switches : {', '.join(self.switches.keys()) if hasattr(self, 'switches') else 'None'}")
        print(f"  Bridges  : {', '.join(self.bridges.keys()) if hasattr(self, 'bridges') else 'None'}")
        print(f"{'='*40}\n")

#test cases
def test_point_to_point():
    print("\n" + "="*50)
    print("  TEST CASE 1: Point-to-Point Connection")
    print("="*50)

    t = Topology("P2P Test")
    t.build_point_to_point("Station_A", "Station_B")
    t.show()

    print("\n--- Sending data ---")
    t.send("Station_A", "Hello", destination="Station_B")


def test_star_topology():
    print("\n" + "="*50)
    print("  TEST CASE 2: Star Topology with Hub")
    print("="*50)

    t = Topology("Star Test")
    t.build_star(
        hub_name="Hub_1",
        device_names=["Station_A", "Station_B", "Station_C", "Station_D", "Station_E"]
    )
    t.show()

    print("\n--- Normal transmission ---")
    t.send("Station_A", "Hi", destination="Station_B")

    print("\n--- Collision scenario ---")
    t.simulate_collision("Hub_1", "Station_A", "Hello", "Station_C", "World")

#DLL test case
def test_switch_star():
    print("\n" + "="*50)
    print("  TEST CASE 3: Switch Star Topology")
    print("="*50)

    t = Topology("Switch Star")
    t.build_switch_star("Switch_1", ["A", "B", "C", "D", "E"])
    t.show()

    # first transmission — switch doesn't know anyone yet, will flood
    print("\n--- First transmission (switch will flood) ---")
    t.dll_send("A", "Hello B", "B")
    t.show_mac_table("Switch_1")

    # second transmission — switch now knows A and B
    print("\n--- Second transmission (switch will forward directly) ---")
    t.dll_send("B", "Hi A", "A")
    t.show_mac_table("Switch_1")

    # demonstrate CSMA/CD
    print("\n--- CSMA/CD Demo ---")
    switch = t.switches["Switch_1"]
    sender1 = t.devices["A"]
    sender2 = t.devices["C"]
    frame1 = Frame(sender1.mac, t.devices["B"].mac, "Hello", 0)
    frame2 = Frame(sender2.mac, t.devices["D"].mac, "World", 0)
    switch.simulate_csma_collision(sender1, frame1, sender2, frame2)

    # demonstrate Go Back N
    print("\n--- Go Back N Demo ---")
    messages = ["Frame0", "Frame1", "Frame2", "Frame3", "Frame4"]
    t.gbn_send("A", messages, "B", window_size=3, drop_prob=0.3)

def test_two_hubs_switch():
    print("\n" + "="*50)
    print("  TEST CASE 4: Two Star Topologies connected via Switch")
    print("="*50)

    t = Topology("Two Stars")

    # build first star
    t.add_hub("Hub_1", 5)
    for name in ["A", "B", "C", "D", "E"]:
        t.add_device(name)
        t.connect(name, "Hub_1")

    # build second star
    t.add_hub("Hub_2", 5)
    for name in ["F", "G", "H", "I", "J"]:
        t.add_device(name)
        t.connect(name, "Hub_2")

    # connect two hubs via switch
    t.add_switch("Switch_1", 2)

    # hubs connect to switch via special devices acting as uplinks
    hub1 = t.hubs["Hub_1"]
    hub2 = t.hubs["Hub_2"]
    switch = t.switches["Switch_1"]

    # link hubs to switch directly
    hub1.uplink = switch
    hub2.uplink = switch

    t.show()

    # report domains
    print("\n--- Network Domains ---")
    print("  Collision Domains : 3")
    print("    → Hub_1 segment (1 collision domain — all share medium)")
    print("    → Hub_2 segment (1 collision domain — all share medium)")
    print("    → Switch uplinks (1 collision domain each port)")
    print("  Broadcast Domains : 1")
    print("    → Switch forwards broadcasts, so all 10 devices are in 1 broadcast domain")

    # send within same hub
    print("\n--- Sending within Hub_1 (A → B) ---")
    t.send("A", "Hello B", destination="B")

    # send across hubs
    print("\n--- Sending across hubs (A → F) ---")
    t.send("A", "Hello F", destination="F")

def test_bridge():
    print("\n" + "="*50)
    print("  TEST CASE 5: Bridge connecting two segments")
    print("="*50)

    t = Topology("Bridge Test")
    for name in ["A", "B", "C", "D", "E", "F"]:
        t.add_device(name)

    t.add_bridge("Bridge_1")
    t.connect_bridge("Bridge_1", ["A", "B", "C"], ["D", "E", "F"])
    t.show()

    # same segment — should be filtered
    print("\n--- A sends to B (same segment — should be FILTERED) ---")
    t.dll_send("A", "Hello B", "B")
    t.show_mac_table("Bridge_1")

    # different segment — should be forwarded
    print("\n--- A sends to D (different segment — should be FORWARDED) ---")
    t.dll_send("A", "Hello D", "D")
    t.show_mac_table("Bridge_1")
    

def run():
    print("\n" + "="*50)
    print("   Network Simulator — Protocol Stack")
    print("="*50)

    print("\nSelect topology:")
    print("  1. Point-to-point")
    print("  2. Star (Hub)")
    print("  3. Switch Star")
    print("  4. Bridge")

    choice = input("\nEnter choice: ").strip()
    t = None

    if choice == "1":
        d1 = input("Enter name of device 1: ").strip()
        d2 = input("Enter name of device 2: ").strip()
        t = Topology("Point-to-Point")
        t.build_point_to_point(d1, d2)

    elif choice == "2":
        hub_name = input("Enter hub name: ").strip()
        names = input("Enter device names (space separated): ").strip().split()
        t = Topology("Star")
        t.build_star(hub_name, names)

    elif choice == "3":
        switch_name = input("Enter switch name: ").strip()
        names = input("Enter device names (space separated): ").strip().split()
        t = Topology("Switch Star")
        t.build_switch_star(switch_name, names)

    elif choice == "4":
        seg1 = input("Enter segment 1 device names (space separated): ").strip().split()
        seg2 = input("Enter segment 2 device names (space separated): ").strip().split()
        t = Topology("Bridge")
        for name in seg1 + seg2:
            t.add_device(name)
        t.add_bridge("Bridge_1")
        t.connect_bridge("Bridge_1", seg1, seg2)

    else:
        print("Invalid choice.")
        return

    t.show()

    # decide which actions are available based on topology
    has_hub = bool(t.hubs)
    has_switch = bool(t.switches)
    has_bridge = bool(t.bridges)

    while True:
        print("\nWhat do you want to do?")
        print("  1. Send a message")
        if has_hub:
            print("  2. Simulate a collision")
        if has_switch:
            print("  3. Go Back N transmission")
            print("  4. Show MAC table")
            print("  5. Simulate CSMA/CD collision")
        print("  6. Exit")

        action = input("\nEnter choice: ").strip()

        if action == "1":
            sender = input("Who is sending? ").strip()
            message = input("Enter message: ").strip()
            destination = input("Enter destination (or press Enter for broadcast): ").strip()
            destination = destination if destination else None

            # automatically route through correct layer
            if has_switch or has_bridge:
                if destination:
                    t.dll_send(sender, message, destination)
                else:
                    print("Broadcast not supported at DLL layer — enter a destination.")
            else:
                t.send(sender, message, destination=destination)

        elif action == "2" and has_hub:
            hub_name = list(t.hubs.keys())[0]
            print(f"Available devices: {', '.join(t.devices.keys())}")
            s1 = input("Enter first sender: ").strip()
            m1 = input("Enter first message: ").strip()
            s2 = input("Enter second sender: ").strip()
            m2 = input("Enter second message: ").strip()
            t.simulate_collision(hub_name, s1, m1, s2, m2)

        elif action == "3" and has_switch:
            sender = input("Who is sending? ").strip()
            destination = input("Enter destination: ").strip()
            n = int(input("How many frames? ").strip())
            messages = [input(f"  Frame {i}: ").strip() for i in range(n)]
            ws = int(input("Window size: ").strip())
            dp = float(input("Drop probability (0.0 to 1.0): ").strip())
            t.gbn_send(sender, messages, destination, ws, dp)

        elif action == "4" and has_switch:
            name = input("Enter switch/bridge name: ").strip()
            t.show_mac_table(name)

        elif action == "5" and has_switch:
            switch_name = list(t.switches.keys())[0]
            print(f"Available devices: {', '.join(t.devices.keys())}")
            s1 = input("Enter first sender: ").strip()
            s2 = input("Enter second sender: ").strip()
            switch = t.switches[switch_name]
            d1 = t.devices[s1]
            d2 = t.devices[s2]
            f1 = Frame(d1.mac, d2.mac, "msg1", 0)
            f2 = Frame(d2.mac, d1.mac, "msg2", 0)
            switch.simulate_csma_collision(d1, f1, d2, f2)

        elif action == "6":
            print("\nExiting simulator. Goodbye!")
            break

        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    run()