import numpy as np
import mpmath as mp
import matplotlib.pyplot as plt

# ============================================================
# High precision
# ============================================================
mp.mp.dps = 80   # 80 decimal digits (~128-bit precision)

# ============================================================
# Parameters
# ============================================================
M        = 4
Nbits    = 40000
sps      = 16
beta     = 0.25
span     = 32

# ============================================================
# RRC filter (mpmath, ultra-precise)
# ============================================================
def rrcosdesign_mp(beta, span, sps):
    N = span * sps
    t = [mp.mpf(n) for n in range(-N//2, N//2 + 1)]
    h = []

    for n in t:
        if n == 0:
            val = (1/mp.sqrt(sps))*((1-beta)+(4*beta/mp.pi))
        elif abs(n*4*beta) == sps:
            val = (beta/mp.sqrt(2*sps))*(
                (1+2/mp.pi)*mp.sin(mp.pi/(4*beta)) +
                (1-2/mp.pi)*mp.cos(mp.pi/(4*beta))
            )
        else:
            num = mp.sin(mp.pi*n*(1-beta)/sps) + \
                  4*beta*n/sps * mp.cos(mp.pi*n*(1+beta)/sps)
            den = mp.pi*n/sps * (1 - (4*beta*n/sps)**2)
            val = (1/mp.sqrt(sps)) * (num/den)
        h.append(val)

    # Normalize to unit energy
    energy = mp.sqrt(mp.fsum([x*x for x in h]))
    h = [x/energy for x in h]

    return np.array([complex(float(x)) for x in h], dtype=np.complex128)

rrc = rrcosdesign_mp(beta, span, sps)
delay_samp = span * sps

# ============================================================
# TX: bits â QPSK â upsample â RRC
# ============================================================
bits = np.random.randint(0, 2, Nbits)
dibits = bits.reshape(-1, 2)

mapping = {
    (0,0):  1+1j,
    (0,1): -1+1j,
    (1,1): -1-1j,
    (1,0):  1-1j,
}
symbols_tx = np.array([mapping[tuple(b)] for b in dibits], dtype=np.complex128)

upsampled = np.zeros(len(symbols_tx)*sps, dtype=np.complex128)
upsampled[::sps] = symbols_tx

tx_wave = np.convolve(upsampled, rrc, mode="full")

# ============================================================
# Ideal channel (no noise)
# ============================================================
rx_wave = tx_wave.copy()

# ============================================================
# RX: matched filter + downsample
# ============================================================
rx_filt = np.convolve(rx_wave, rrc, mode="full")
rx_sym_raw = rx_filt[delay_samp::sps]
rx_sym_raw = rx_sym_raw[:len(symbols_tx)]

# ============================================================
# Complex gain/phase correction
# ============================================================
a = np.sum(rx_sym_raw * np.conjugate(symbols_tx)) / np.sum(np.abs(symbols_tx)**2)
rx_sym = rx_sym_raw / a

# ============================================================
# EVM
# ============================================================
error = rx_sym - symbols_tx
evm_rms = np.sqrt(np.sum(np.abs(error)**2) / np.sum(np.abs(symbols_tx)**2))
evm_percent = evm_rms * 100

print(f"EVM RMS: {evm_rms:.12e}")
print(f"EVM %: {evm_percent:.12e}")

# ============================================================
# Constellation
# ============================================================
plt.figure(figsize=(6,6))
plt.scatter(np.real(rx_sym), np.imag(rx_sym), s=3, alpha=0.4)
plt.title("QPSK Constellation (128-bit, span=32, sps=16, no noise)")
plt.xlabel("I")
plt.ylabel("Q")
plt.grid(True)
plt.axis('equal')
plt.show()
