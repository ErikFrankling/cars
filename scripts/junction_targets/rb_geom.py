"""Ring centre and radius from where cars actually drive, starting from a rough hand-read guess."""
import numpy as np


def refine(X, Y, cx, cy, R):
    c0 = (cx, cy)
    for w in (4, 3, 2.5, 2.5):
        m = np.abs(np.hypot(X - cx, Y - cy) - R) < w
        A = np.c_[2 * X[m], 2 * Y[m], np.ones(m.sum())]
        b = (X[m] - c0[0])**2 + (Y[m] - c0[1])**2
        A[:, 0] = 2 * (X[m] - c0[0])
        A[:, 1] = 2 * (Y[m] - c0[1])
        s = np.linalg.lstsq(A, b, rcond=None)[0]
        cx, cy = c0[0] + s[0], c0[1] + s[1]
        R = float(np.sqrt(s[2] + s[0]**2 + s[1]**2))
    return cx, cy, R
