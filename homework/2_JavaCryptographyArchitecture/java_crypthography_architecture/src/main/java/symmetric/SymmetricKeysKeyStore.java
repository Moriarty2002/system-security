package symmetric;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.KeyStore;
import java.security.KeyStore.*;
import java.security.SecureRandom;

public class SymmetricKeysKeyStore {

    private static final String CONFIG_DIR = "src/main/resources/symmetric";
    private static final String KEYSTORE_FILE = "keystore.jks";
    private static final Path KEYSTORE_PATH = Paths.get(CONFIG_DIR, KEYSTORE_FILE);

    //JCEKS use triple DES and MD5 with salt, more secure than default JKS
    private static final String KEYSTORE_TYPE = "JCEKS";
    private static final char[] KEYSTORE_PASSWORD = "PSW_FROM_ENV_VAR".toCharArray(); // get password from env var
    private static final String KEY_ALIAS = "aes-key";
    private static final String IV_ALIAS = "aes-iv";
    private static final String ALGORITHM = "AES";
    private static final String CIPHER_TRANSFORMATION = "AES/CBC/PKCS5Padding";

    static void main(String[] args) throws Exception {
        // generate key and init vector
        KeyGenerator keyGen = KeyGenerator.getInstance(ALGORITHM);
        keyGen.init(256);
        SecretKey secretKey = keyGen.generateKey();

        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        IvParameterSpec ivSpec = new IvParameterSpec(iv);

        storeKeyAndIv(secretKey, ivSpec);

        System.out.println("Generated key: " + java.util.Base64.getEncoder().encodeToString(secretKey.getEncoded()));
        System.out.println("Generated IV:  " + java.util.Base64.getEncoder().encodeToString(ivSpec.getIV()));
        System.out.println("-------------------------------------------------");

        // encrypt
        String plainText = "! this is a msg !";
        Cipher cipherEncrypt = Cipher.getInstance(CIPHER_TRANSFORMATION);
        cipherEncrypt.init(Cipher.ENCRYPT_MODE, secretKey, ivSpec);
        byte[] cipherText = cipherEncrypt.doFinal(plainText.getBytes());

        System.out.println("Original text: " + plainText);
        System.out.println("Encrypted text: " + java.util.Base64.getEncoder().encodeToString(cipherText));
        System.out.println("-------------------------------------------------");

        // decrypt
        SecretKey loadedKey = loadKey();
        IvParameterSpec loadedIvSpec = loadIv();

        System.out.println("Loaded key: " + java.util.Base64.getEncoder().encodeToString(loadedKey.getEncoded()));
        System.out.println("Loaded IV:  " + java.util.Base64.getEncoder().encodeToString(loadedIvSpec.getIV()));

        Cipher cipherDecrypt = Cipher.getInstance(CIPHER_TRANSFORMATION);
        cipherDecrypt.init(Cipher.DECRYPT_MODE, loadedKey, loadedIvSpec);
        String decryptedText = new String(cipherDecrypt.doFinal(cipherText));

        System.out.println("Deciphered text: " + decryptedText);
    }

    public static void storeKeyAndIv(SecretKey key, IvParameterSpec ivSpec) throws Exception {
        Files.createDirectories(KEYSTORE_PATH.getParent());

        KeyStore ks = loadOrCreateKeyStore();

        // store the AES key
        SecretKeyEntry keyEntry = new SecretKeyEntry(key);
        ProtectionParameter protParam = new PasswordProtection(KEYSTORE_PASSWORD);
        ks.setEntry(KEY_ALIAS, keyEntry, protParam);

        // store the IV as a SecretKeySpec (store raw bytes)
        SecretKeySpec ivKey = new SecretKeySpec(ivSpec.getIV(), ALGORITHM);
        SecretKeyEntry ivEntry = new SecretKeyEntry(ivKey);
        ks.setEntry(IV_ALIAS, ivEntry, protParam);

        try (OutputStream out = Files.newOutputStream(KEYSTORE_PATH)) {
            ks.store(out, KEYSTORE_PASSWORD);
        }
    }

    public static SecretKey loadKey() throws Exception {
        KeyStore ks = loadOrCreateKeyStore();
        ProtectionParameter protParam = new PasswordProtection(KEYSTORE_PASSWORD);
        SecretKeyEntry entry = (SecretKeyEntry) ks.getEntry(KEY_ALIAS, protParam);
        if (entry == null) {
            throw new Exception("Key alias not found: " + KEY_ALIAS);
        }
        return entry.getSecretKey();
    }

    public static IvParameterSpec loadIv() throws Exception {
        KeyStore ks = loadOrCreateKeyStore();
        ProtectionParameter protParam = new PasswordProtection(KEYSTORE_PASSWORD);
        SecretKeyEntry entry = (SecretKeyEntry) ks.getEntry(IV_ALIAS, protParam);
        if (entry == null) {
            throw new Exception("IV alias not found: " + IV_ALIAS);
        }
        SecretKeySpec ivKey = (SecretKeySpec) entry.getSecretKey();
        return new IvParameterSpec(ivKey.getEncoded());
    }

    private static KeyStore loadOrCreateKeyStore() throws Exception {
        KeyStore ks = KeyStore.getInstance(KEYSTORE_TYPE);
        if (Files.exists(KEYSTORE_PATH)) {
            try (InputStream in = Files.newInputStream(KEYSTORE_PATH)) {
                ks.load(in, KEYSTORE_PASSWORD);
            }
        } else {
            ks.load(null, KEYSTORE_PASSWORD); // initialize empty keystore
        }
        return ks;
    }
}
