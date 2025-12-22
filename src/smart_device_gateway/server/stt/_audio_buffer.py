# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import numpy as np


class RingBuffer:
    def __init__(self, capacity, dtype=np.float32):
        """
        Initializes the ring buffer with a fixed capacity and data type.

        Args:
            capacity (int): The maximum number of samples the buffer can hold.
            dtype: The data type of the buffer (default is np.float32 for audio data).
        """
        self.capacity = capacity
        # Initialize the buffer with zeros
        self.buffer = np.zeros(capacity, dtype=dtype)
        self.head = 0  # Points to the oldest sample
        self.tail = 0  # Points to the next insertion position
        self.size = 0  # Number of elements in the buffer
        self.dtype = dtype

    def is_empty(self):
        """
        Checks if the buffer is empty.

        Returns:
            bool: True if the buffer is empty, False otherwise.
        """
        return self.size == 0

    def is_full(self):
        """
        Checks if the buffer is full.

        Returns:
            bool: True if the buffer is full, False otherwise.
        """
        return self.size == self.capacity

    def write(self, data):
        """
        Writes a chunk of audio data to the buffer.

        Args:
            data (np.ndarray): The audio data to be added to the buffer.

        Raises:
            ValueError: If there is not enough space in the buffer to write the data.
        """
        if data is None:
            return

        data_len = len(data)
        if data_len > self.capacity - self.size:
            raise ValueError("Not enough space in buffer to write data")

        # Determine the split point if the data wraps around
        end_space = self.capacity - self.tail
        if data_len <= end_space:
            self.buffer[self.tail:self.tail + data_len] = data
        else:
            self.buffer[self.tail:] = data[:end_space]
            self.buffer[:data_len - end_space] = data[end_space:]

        self.tail = (self.tail + data_len) % self.capacity
        self.size += data_len

    def read(self, num_samples):
        """
        Reads and returns a chunk of audio data from the buffer.

        Args:
            num_samples (int): The number of samples to read from the buffer.

        Returns:
            np.ndarray: The read audio data.

        Raises:
            ValueError: If there are not enough samples in the buffer to read.
        """
        if num_samples > self.size:
            #print("Not enough samples in buffer to read")
            return None

        # Determine the split point if the data wraps around
        end_space = self.capacity - self.head
        if num_samples <= end_space:
            data = self.buffer[self.head:self.head + num_samples]
        else:
            data = np.concatenate(
                (self.buffer[self.head:], self.buffer[:num_samples - end_space]))

        self.head = (self.head + num_samples) % self.capacity
        self.size -= num_samples

        return data

    def __len__(self):
        """
        Returns the number of elements currently in the buffer.

        Returns:
            int: The number of elements in the buffer.
        """
        return self.size

    def __repr__(self):
        """
        Returns a string representation of the buffer for debugging.

        Returns:
            str: A string representation of the buffer.
        """
        if self.is_empty():
            return "AudioRingBuffer([])"

        # Display only the data currently in the buffer for clarity
        if self.head < self.tail:
            items = self.buffer[self.head:self.tail].tolist()
        else:
            items = (self.buffer[self.head:].tolist() +
                     self.buffer[:self.tail].tolist())

        return f"AudioRingBuffer({items})"

    def reset(self):
        """
        Resets the buffer to an empty state.
        """
        self.head = 0
        self.tail = 0
        self.size = 0
        self.buffer.fill(0)  # Optional: Clear the buffer data
