package asymmetric;

import javax.crypto.Cipher;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.Base64;

public class AsymmetricKeysSimple {

    static void main() throws Exception {
        // ## encrypt example
        System.out.println("--- CONFIDENTIALITY ---");
        // generate KeyPair (RSA 3072 bits key)
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(3072);
        KeyPair keyPair = kpg.generateKeyPair();

        // encrypt with public key
        PublicKey pubKey = keyPair.getPublic();
        String plaintext = "! This is a msg !";
        Cipher encryptCipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
        encryptCipher.init(Cipher.ENCRYPT_MODE, pubKey);
        byte[] cipherBytes = encryptCipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
        System.out.println("Encrypted (base64 for human readable) = " + Base64.getEncoder().encodeToString(cipherBytes));

        // decrypt with private key
        PrivateKey privKey = keyPair.getPrivate();
        Cipher decryptCipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
        decryptCipher.init(Cipher.DECRYPT_MODE, privKey);
        byte[] decrypted = decryptCipher.doFinal(cipherBytes);
        System.out.println("Decrypted text = " + new String(decrypted, StandardCharsets.UTF_8));
        
        // ## sign example 
        System.out.println("\n--- INTEGRITY ---");

        String originalMessage = "! This is a msg to be signed !";
        byte[] messageBytes = originalMessage.getBytes(StandardCharsets.UTF_8);

        // sign with private key
        // Get a Signature instance. "SHA256withRSA" is a standard algorithm.
        // It automatically creates a SHA-256 hash of the data and then "encrypts" that hash with the private key.
        Signature sig = Signature.getInstance("SHA256withRSA");
        sig.initSign(privKey);
        sig.update(messageBytes);
        // Generate the signature
        byte[] signatureBytes = sig.sign();
        System.out.println("Original Message: " + originalMessage);
        System.out.println("Signature (base64): " + Base64.getEncoder().encodeToString(signatureBytes));

        // verify with public key
        sig.initVerify(pubKey);
        // pass in the clear text message data (NOT the signature)
        sig.update(messageBytes);
        // verify the signature against the data
        boolean isVerified = sig.verify(signatureBytes);
        System.out.println("Verification successful: " + isVerified);

        // ## verification failure example
        System.out.println("--- failed validation");
        String tamperedMessage = "! This is a TAMPERED msg !";
        sig.initVerify(pubKey);
        sig.update(tamperedMessage.getBytes(StandardCharsets.UTF_8));
        boolean isTamperedVerified = sig.verify(signatureBytes);
        System.out.println("Tampered message verification successful: " + isTamperedVerified);
    }
}