package asymmetric;

import javax.crypto.Cipher;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.Base64;

public class AsymmetricKeysSimple {

    static void main() throws Exception {
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
    }
}