////////////////////////////////////////////////////////////////////////////////////////////////////////
///
/// @author     Bruno Van de Velde (bruno@texus.me)
/// @copyright  This file is licensed under the GNU General Public License v2.
///
////////////////////////////////////////////////////////////////////////////////////////////////////////

#include "sniffer_serial_receive.hpp"
#include "sniffer_serial_send.hpp"

namespace Sniffer
{
    bool     receivingStatus = false;
    bool     escaping = false;
    uint16_t crc = CRC_INIT;
    uint8_t  message[SERIAL_RX_MAX_MESSAGE_LEN];
    uint8_t  messageLen = 0;
    uint16_t previousReceivedIndex = INVALID_RECEIVED_INDEX;

    static volatile uint8_t uartRxBuffer[SERIAL_RX_BUFFER_LEN];
    static volatile uint8_t uartRxBufferIndexWrite = 0;
    static volatile uint8_t uartRxBufferIndexRead = 0;

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    void SerialReceive::uartByteReceived()
    {
        uartRxBuffer[uartRxBufferIndexWrite] = uart.readByte();

        uartRxBufferIndexWrite++;
        if (uartRxBufferIndexWrite == sizeof(uartRxBuffer))
            uartRxBufferIndexWrite = 0;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    void SerialReceive::receive()
    {
        while (uartRxBufferIndexRead != uartRxBufferIndexWrite)
        {
            processByte(uartRxBuffer[uartRxBufferIndexRead]);

            uartRxBufferIndexRead++;
            if (uartRxBufferIndexRead == sizeof(uartRxBuffer))
                uartRxBufferIndexRead = 0;
        }
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::processByte(uint8_t byte)
    {
        // Check if the byte is special (start or end byte)
        if (byte == HDLC_FLAG)
        {
            // Check if the frame is complete
            if (receivingStatus)
                receivedEndByte();
            else // This is the opening byte
                receivedStartByte();
        }
        else // Normal data byte
        {
            // Put the byte in the receive buffer
            if (receivingStatus && messageLen < SERIAL_RX_MAX_MESSAGE_LEN)
                addByteToBuffer(byte);
            else
            {
                // Something went wrong, start retransmitting
                bufferIndexSerialSend = bufferIndexAcked;
                receivingStatus = false;
                messageLen = 0;
            }
        }
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedStartByte()
    {
        receivingStatus = true;
        escaping = false;
        messageLen = 0;
        crc = CRC_INIT;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedEndByte()
    {
        // Detect out of sync
        if (messageLen == 0)
        {
            receivedStartByte();
            bufferIndexSerialSend = bufferIndexAcked;
            return;
        }

        // You are not supposed to pass here in escaping mode or with a too short message
        bool validMessage = false;
        if (!escaping && (messageLen >= 4)) // minimum packet size = 1 byte type + 1 byte length + 2 byte crc
        {
            if (crc == 0) // Calculating CRC of packet bytes + CRC bytes always results 0 for correct CRC
            {
                // Make sure the length byte is correct (value of length byte does not include type and length bytes)
                if (messageLen == message[1] + 2)
                {
                    // Find out what message we received and act acordingly
                    validMessage = decodeReceivedMessage();
                }
            }
        }

        // Start retransmitting if there was something wrong with the message
        if (!validMessage)
            bufferIndexSerialSend = bufferIndexAcked;

        receivingStatus = false;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::addByteToBuffer(uint8_t byte)
    {
        if (byte == HDLC_ESCAPE)
        {
            if (!escaping)
            {
                escaping = true;
            }
            else // Something is wrong
            {
                bufferIndexSerialSend = bufferIndexAcked;
                receivingStatus = false;
            }
        }
        else // The byte is not special
        {
            if (escaping)
            {
                byte = byte ^ HDLC_ESCAPE_MASK;
                escaping = false;
            }

            message[messageLen++] = byte;
            crc = crcCalculationStep(byte, crc);
        }
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline bool SerialReceive::decodeReceivedMessage()
    {
        if ((message[0] == SerialDataType::Ack) && (message[1] == ACK_MESSAGE_LENGTH))
            receivedACK();
        else if ((message[0] == SerialDataType::Nack) && (message[1] == NACK_MESSAGE_LENGTH))
            receivedNACK();
        else if ((message[0] == SerialDataType::Reset) && (message[1] == RESET_MESSAGE_LENGTH))
            receivedRESET();
        else if ((message[0] == SerialDataType::Stop) && (message[1] == STOP_MESSAGE_LENGTH))
            receivedSTOP();
        else
            return false;

        return true;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedACK()
    {
        uint16_t receivedIndex = readUint16(message, ACK_INDEX_OFFSET);
        uint16_t receivedSeqNr = readUint16(message, ACK_SEQNR_OFFSET);

        // Ignore duplicate messages
        if (previousReceivedIndex == receivedIndex)
            return;

        // Validate the received index which has to lie within the unacked area and make sure the sequence number matches with it
        if (checkReceivedIndexAndSeqNr(receivedIndex, receivedSeqNr))
        {
            // Move the acked index forward
            bufferIndexAcked = receivedIndex + buffer[receivedIndex];

            // Keep track of the last received index
            previousReceivedIndex = receivedIndex;
        }
        else
            receivedInvalidMessage();
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedNACK()
    {
        uint16_t receivedIndex = readUint16(message, NACK_INDEX_OFFSET);
        uint16_t receivedSeqNr = readUint16(message, NACK_SEQNR_OFFSET);

        // Validate the received index which has to lie within the unacked area or be the same as in the last ACK/NACK
        bool validIndex;
        if (previousReceivedIndex == receivedIndex)
            validIndex = true;
        else
            validIndex = checkReceivedIndexAndSeqNr(receivedIndex, receivedSeqNr);

        if (validIndex)
        {
            // Move the acked index forward (start from beginning again when reaching the end of the buffer)
            uint8_t packetLength = buffer[receivedIndex];
            bufferIndexAcked = receivedIndex + packetLength;
            if (buffer[bufferIndexAcked] == END_OF_BUFFER_BYTE)
                bufferIndexAcked = 0;

            // Resend everything up to the last acked packet
            bufferIndexSerialSend = bufferIndexAcked;

            // Keep track of the last received index
            previousReceivedIndex = receivedIndex;
        }
        else
            receivedInvalidMessage();
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedRESET()
    {
        // Disable radio interrupts while resetting values
        IntDisable(INT_RFCORERTX);

        // Turn off warning lights
        led_green.on();
        led_yellow.off();
        led_orange.off();
        led_red.off();

        // Empty buffer and reset sequence number
        bufferIndexRadio = 0;
        bufferIndexSerialSend = 0;
        bufferIndexAcked = 0;
        seqNr = 0;

        // Verify that the received channel is within the correct range
        uint8_t channel = message[RESET_CHANNEL_OFFSET];
        if (channel >= 11 && channel <= 26)
        {
            // Set the requested channel
            radio.setChannel(channel);

            // Send the READY message
            SerialSend::sendReadyPacket();

            // Allow new radio packets now
            CC2538_RF_CSP_ISFLUSHRX();
            IntEnable(INT_RFCORERTX);
            CC2538_RF_CSP_ISRXON();
        }
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedSTOP()
    {
        // Disable radio interrupts and clear the radio buffer
        IntDisable(INT_RFCORERTX);
        CC2538_RF_CSP_ISFLUSHRX();

        led_green.off();
        led_yellow.off();
        led_orange.off();
        led_red.off();

        // Empty buffer and reset sequence number
        bufferIndexRadio = 0;
        bufferIndexSerialSend = 0;
        bufferIndexAcked = 0;
        seqNr = 0;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline void SerialReceive::receivedInvalidMessage()
    {
        led_orange.on();
        bufferIndexSerialSend = bufferIndexAcked;
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////////

    inline bool SerialReceive::checkReceivedIndexAndSeqNr(uint16_t receivedIndex, uint16_t receivedSeqNr)
    {
        // Caching the radio buffer is required because we do two if checks directly after each other.
        // If a radio interrupt occurred exactly between these lines and it would move the radio index from
        // the end to the beginning of the buffer then the received index would be incorrectly discarted.
        // Caching it has no influence because the received index has to be smaller than the old radio index.
        // The radio index can never pass the acked index so an up-to-date radio index is not relevant in these checks.
        uint16_t cachedBufferIndexRadio = bufferIndexRadio;

        if (receivedIndex >= sizeof(buffer))
        {
            return false;
        }
        else if (bufferIndexAcked > cachedBufferIndexRadio) // around end and start of buffer
        {
            if ((receivedIndex < bufferIndexAcked) && (receivedIndex > cachedBufferIndexRadio))
                return false;
        }
        else // if (bufferIndexAcked <= cachedBufferIndexRadio)
        {
            if ((receivedIndex < bufferIndexAcked) || (receivedIndex > cachedBufferIndexRadio))
                return false;
        }

        uint16_t seqNrInBuffer = readUint16(buffer, receivedIndex + BUFFER_SEQNR_OFFSET);

        if (seqNrInBuffer != receivedSeqNr)
            return false;

        return true;
    }
}
