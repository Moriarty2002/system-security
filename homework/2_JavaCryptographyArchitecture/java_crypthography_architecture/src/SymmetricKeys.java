import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import java.security.SecureRandom;
import java.util.Base64;

public class SymmetricKeys {
    public static void main(String[] args) throws Exception {
        // 1. Genera una chiave simmetrica (AES a 256 bit)
        KeyGenerator keyGen = KeyGenerator.getInstance("AES");
        keyGen.init(256);
        SecretKey secretKey = keyGen.generateKey();

        System.out.println("Chiave generata: " + Base64.getEncoder().encodeToString(secretKey.getEncoded()));

        // 2. Prepara il Cipher (Algoritmo/Modalità/Padding)
        // Usiamo CBC che richiede un Vettore di Inizializzazione (IV)
        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        IvParameterSpec ivSpec = new IvParameterSpec(iv);

        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");

        // 3. Critta
        String plainText = "Questo è un messaggio segreto!";
        cipher.init(Cipher.ENCRYPT_MODE, secretKey, ivSpec);
        byte[] cipherText = cipher.doFinal(plainText.getBytes("UTF-8"));

        System.out.println("Testo crittato: " + Base64.getEncoder().encodeToString(cipherText));

        // 4. Decritta
        // Per decrittare, devi usare la STESSA chiave e lo STESSO IV
        cipher.init(Cipher.DECRYPT_MODE, secretKey, ivSpec);
        byte[] decryptedText = cipher.doFinal(cipherText);

        System.out.println("Testo decrittato: " + new String(decryptedText, "UTF-8"));
    }
}